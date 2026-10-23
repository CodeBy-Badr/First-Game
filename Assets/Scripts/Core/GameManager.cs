// =============================================================================
// FILE:     GameManager.cs
// PATH:     Assets/Scripts/Core/GameManager.cs
// PURPOSE:  Central engine switchboard. Owns GameMode, PlayerProfile, and the
//           15-slot character availability pool. Survives all scene loads via
//           DontDestroyOnLoad. Thread-safe singleton via double-checked locking
//           with volatile field and Interlocked.Exchange for teardown.
//           Mobile-safe: no per-frame allocations, no coroutine boxing.
// =============================================================================

using System;
using UnityEngine;
using UnityEngine.SceneManagement;
using LostIsland.Data;

namespace LostIsland.Core
{
    // -------------------------------------------------------------------------
    // GameMode — top-level discriminator that drives subsystem activation.
    // -------------------------------------------------------------------------
    public enum GameMode { None, Offline, Online }

    // -------------------------------------------------------------------------
    // GameManager — persistent, thread-safe singleton MonoBehaviour.
    // One and only one instance lives across all scenes.
    // -------------------------------------------------------------------------
    [DisallowMultipleComponent]
    public sealed class GameManager : MonoBehaviour
    {
        // =====================================================================
        // Singleton — double-checked locking pattern
        // =====================================================================

        // volatile: prevents JIT from reordering writes across threads,
        // ensuring cross-thread visibility of the fully-constructed reference.
        private static volatile GameManager _instance;

        // Lock target is a plain object — cheapest possible mutex allocation.
        private static readonly object _lock = new object();

        /// <summary>
        /// Thread-safe singleton accessor using double-checked locking.
        /// Safe to call from background threads (e.g., network receive loops).
        /// Returns null gracefully after OnDestroy to avoid stale-state bugs.
        /// </summary>
        public static GameManager Instance
        {
            get
            {
                // First check (no lock) avoids lock overhead on the hot path.
                if (_instance != null) return _instance;

                lock (_lock)
                {
                    // Re-check inside the lock: another thread may have written
                    // _instance between the outer null-check and acquiring the lock.
                    if (_instance == null)
                    {
                        _instance = FindObjectOfType<GameManager>();

                        if (_instance == null)
                        {
                            var go = new GameObject("[GameManager]");
                            _instance = go.AddComponent<GameManager>();
                        }
                    }
                }
                return _instance;
            }
        }

        // =====================================================================
        // Public State
        // =====================================================================

        /// <summary>Active game mode. Drives subsystem instantiation throughout the game.</summary>
        public GameMode Mode { get; private set; }

        /// <summary>Profile of the local human player for this session.</summary>
        public PlayerProfile LocalPlayer { get; private set; }

        // =====================================================================
        // Character Slot Pool
        // =====================================================================

        // bool[] is the lightest structure possible for a 15-element availability map.
        // Index maps 1:1 with BoyId enum ordinal. true = free, false = claimed.
        private readonly bool[] _slotAvailable = new bool[BoyRoster.ROSTER_SIZE];

        // =====================================================================
        // Scene Name Constants
        // =====================================================================
        private const string SCENE_PROLOGUE = "StormPrologue";
        private const string SCENE_ISLAND   = "IslandSurvival";
        private const string SCENE_LOBBY    = "MultiplayerLobby";

        // =====================================================================
        // Events — System.Action delegates (lighter than UnityEvent, no boxing)
        // =====================================================================

        /// <summary>
        /// Fires when the game mode transitions (None to Offline or Online).
        /// Listeners: UI controllers, network manager, AI bootstrap.
        /// Listeners must unsubscribe in their OnDestroy to prevent leaks.
        /// </summary>
        public event Action<GameMode> OnGameModeChanged;

        /// <summary>
        /// Fires when the boat wrecks and the island survival loop must begin.
        /// Listeners: SceneLoader, IslandBootstrapper.
        /// </summary>
        public event Action OnIslandSurvivalStart;

        // =====================================================================
        // Unity Lifecycle
        // =====================================================================

        private void Awake()
        {
            // Destroy any duplicate that arrives via additive scene loading.
            if (_instance != null && _instance != this)
            {
                Destroy(gameObject);
                return;
            }

            _instance = this;
            DontDestroyOnLoad(gameObject);
            Mode = GameMode.None;
            InitializeSlots();

            // Bootstrap the main-thread dispatcher before any subsystem
            // tries to use it. Must be called on the Unity main thread.
            UnityThread.Initialize();
        }

        private void OnDestroy()
        {
            // Direct volatile write — safe and warning-free.
            // Interlocked.Exchange(ref volatile) triggers CS0420 because passing
            // a volatile field by ref strips the volatile qualifier. A plain
            // assignment to a volatile reference field is already atomic on all
            // .NET / Mono platforms (ECMA-335 guarantee), so no Interlocked needed.
            if (_instance == this)
                _instance = null;

            // Release all delegate references to prevent listener leaks.
            OnGameModeChanged     = null;
            OnIslandSurvivalStart = null;
        }

        // =====================================================================
        // Initialization
        // =====================================================================

        /// <summary>Marks all 15 character slots as available.</summary>
        private void InitializeSlots()
        {
            for (int i = 0; i < BoyRoster.ROSTER_SIZE; i++)
                _slotAvailable[i] = true;
        }

        // =====================================================================
        // Public API — Session Control
        // =====================================================================

        /// <summary>
        /// Starts a single-player offline session for the chosen character.
        /// Locks the slot, sets mode, then loads the storm prologue scene.
        /// </summary>
        public void StartOfflineSession(BoyId chosenBoy)
        {
            if (Mode != GameMode.None)
            {
                Debug.LogWarning("[GameManager] Session already active. Ignoring StartOfflineSession.");
                return;
            }

            LocalPlayer = PlayerProfile.CreateOffline(chosenBoy);
            ClaimSlot(chosenBoy);
            SetMode(GameMode.Offline);
            Debug.Log("[GameManager] Offline session started: " + LocalPlayer.ToString());
            LoadSceneAsync(SCENE_PROLOGUE);
        }

        /// <summary>
        /// Starts an online session once the backend server confirms slot reservation.
        /// </summary>
        /// <param name="sessionId">GUID issued by the matchmaking server.</param>
        /// <param name="displayName">Player's chosen display name.</param>
        /// <param name="chosenBoy">Character slot confirmed by the server.</param>
        public void StartOnlineSession(Guid sessionId, string displayName, BoyId chosenBoy)
        {
            if (Mode != GameMode.None)
            {
                Debug.LogWarning("[GameManager] Session already active. Ignoring StartOnlineSession.");
                return;
            }

            LocalPlayer = PlayerProfile.CreateOnline(sessionId, displayName, chosenBoy);
            ClaimSlot(chosenBoy);
            SetMode(GameMode.Online);
            Debug.Log("[GameManager] Online session started: " + LocalPlayer.ToString());
            LoadSceneAsync(SCENE_LOBBY);
        }

        /// <summary>
        /// Called by StormPrologue when boatStability reaches zero.
        /// Deterministically transitions to the island survival map.
        /// Thread-safe — marshals the call to the main thread if needed.
        /// </summary>
        public void TriggerIslandSurvival()
        {
            // Marshal to the main thread so all Unity API calls are safe.
            if (!UnityThread.IsMainThread)
            {
                UnityThread.Dispatch(TriggerIslandSurvivalInternal);
                return;
            }
            TriggerIslandSurvivalInternal();
        }

        private void TriggerIslandSurvivalInternal()
        {
            Debug.Log("[GameManager] Boat wrecked. Transitioning to island survival.");
            // C# 4.0 compatible null check — no ?. operator allowed.
            if (OnIslandSurvivalStart != null)
                OnIslandSurvivalStart();
            LoadSceneAsync(SCENE_ISLAND);
        }

        /// <summary>
        /// Resets all runtime session state. Call before starting a new session.
        /// </summary>
        public void ResetSession()
        {
            InitializeSlots();
            LocalPlayer = default(PlayerProfile); // C# 4.0: explicit type required
            SetMode(GameMode.None);
            Debug.Log("[GameManager] Session reset.");
        }

        // =====================================================================
        // Public API — Slot Queries
        // =====================================================================

        /// <summary>Returns true if the character slot is unclaimed. O(1), zero alloc.</summary>
        public bool IsSlotAvailable(BoyId id)
        {
            return _slotAvailable[(int)id];
        }

        // =====================================================================
        // Private Helpers
        // =====================================================================

        private void SetMode(GameMode newMode)
        {
            Mode = newMode;
            // C# 4.0 compatible null check — no ?. operator allowed.
            if (OnGameModeChanged != null)
                OnGameModeChanged(newMode);
        }

        /// <summary>Marks a character slot as taken. Idempotent, zero allocation.</summary>
        private void ClaimSlot(BoyId id)
        {
            _slotAvailable[(int)id] = false;
        }

        /// <summary>
        /// Non-blocking async scene load — prevents main-thread stalls that are
        /// especially costly on 4 GB RAM devices where streaming takes longer.
        /// </summary>
        private void LoadSceneAsync(string sceneName)
        {
            SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Single);
        }
    }
}
