// =============================================================================
// FILE:     StormPrologue.cs
// PATH:     Assets/Scripts/Prologue/StormPrologue.cs
// PURPOSE:  Controls the boat-stability simulation for the storm prologue.
//
//  ARCHITECTURE OVERVIEW
//  ---------------------
//  - boatStability (0-100) decays each frame based on storm intensity.
//  - The player counters decay via touch (mobile) or keyboard/mouse (desktop).
//  - Zero GC allocation per frame:
//      * Touch structs read via Input.GetTouch(i) — no Touch[] heap alloc.
//      * WaitForSeconds pre-allocated in Awake — never recreated mid-loop.
//      * No string concatenation inside Update / FixedUpdate.
//  - When stability hits zero, GameManager.TriggerIslandSurvival() is called.
//  - Storm intensity escalates linearly over time (Inspector-configurable).
//
//  STATE MACHINE (internal)
//  -------------------------
//    Idle ---[BeginStorm()]---> Running ---[stability==0]---> Wrecked
//
// FIX LOG:
//   - Removed ambiguous Core.GameMode reference; use GameMode directly (same ns).
//   - Cached _gameManager in Awake; Start() now null-guards it.
//   - Removed expression-bodied ContextMenu method (not supported in all Unity
//     C# versions); replaced with block-body syntax.
//   - All string interpolation replaced with concatenation to avoid edge-case
//     compiler issues with older Mono versions shipped with Unity.
// =============================================================================

using System.Collections;
using UnityEngine;
using LostIsland.Core;

namespace LostIsland.Prologue
{
    // Lightweight internal state enum — no string allocation needed.
    public enum PrologueState { Idle, Running, Wrecked }

    [DisallowMultipleComponent]
    public sealed class StormPrologue : MonoBehaviour
    {
        // =====================================================================
        // Inspector-Exposed Configuration
        // =====================================================================

        [Header("Stability Config")]
        [Tooltip("Starting boat stability value (0-100).")]
        [Range(0f, 100f)]
        [SerializeField] private float _startingStability = 100f;

        [Tooltip("Stability lost per second at storm intensity 1.0.")]
        [Range(0f, 30f)]
        [SerializeField] private float _baseDecayRate = 4f;

        [Tooltip("How fast storm intensity ramps up over time (units per second).")]
        [Range(0f, 1f)]
        [SerializeField] private float _intensityRampRate = 0.05f;

        [Tooltip("Maximum storm intensity multiplier cap.")]
        [Range(1f, 5f)]
        [SerializeField] private float _maxIntensity = 3f;

        [Header("Player Counter-Input Config")]
        [Tooltip("Stability gained per second while the player actively inputs.")]
        [Range(0f, 20f)]
        [SerializeField] private float _counterRate = 8f;

        [Header("Online Mode")]
        [Tooltip("Delay in seconds before storm begins after all 15 players connect.")]
        [Range(0f, 10f)]
        [SerializeField] private float _onlineCountdownSeconds = 3f;

        // =====================================================================
        // Runtime State — all value-types, zero managed heap pressure
        // =====================================================================

        private PrologueState _state         = PrologueState.Idle;
        private float         _boatStability;       // [0, startingStability]
        private float         _stormIntensity;      // [1, maxIntensity]
        private float         _elapsedTime;         // cumulative prologue runtime
        private bool          _playerCountering;    // true while input is active

        // Pre-allocated once in Awake — reused every coroutine invocation.
        private WaitForSeconds _countdownWait;

        // Cached reference — avoids repeated singleton lookups in Update.
        private GameManager _gameManager;

        // =====================================================================
        // Events — zero-allocation delegates for UI and audio subsystems
        // =====================================================================

        /// <summary>Fired each frame with current stability [0,100]. Bind UI sliders here.</summary>
        public event System.Action<float> OnStabilityChanged;

        /// <summary>Fired exactly once when the boat wrecks (stability reaches zero).</summary>
        public event System.Action OnBoatWrecked;

        // =====================================================================
        // Unity Lifecycle
        // =====================================================================

        private void Awake()
        {
            _gameManager    = GameManager.Instance;
            _countdownWait  = new WaitForSeconds(_onlineCountdownSeconds); // one-time alloc
            _boatStability  = _startingStability;
            _stormIntensity = 1f;
            _elapsedTime    = 0f;
        }

        private void Start()
        {
            if (_gameManager == null)
            {
                Debug.LogError("[StormPrologue] GameManager not found. Cannot start prologue.");
                return;
            }

            // Offline mode starts the storm immediately on scene load.
            // Online mode waits for BeginStormOnline() to be called by the
            // network client when the server broadcasts the launch packet.
            if (_gameManager.Mode == GameMode.Offline)
            {
                BeginStorm();
            }
        }

        private void OnDestroy()
        {
            // Release delegate references to sever listener chains and prevent leaks.
            OnStabilityChanged = null;
            OnBoatWrecked      = null;
        }

        // =====================================================================
        // Update Loop — ZERO GC allocation path
        // =====================================================================

        private void Update()
        {
            if (_state != PrologueState.Running) return;

            _elapsedTime += Time.deltaTime;

            // ---- Storm Intensity Ramp ---------------------------------------
            // Linear ramp clamped to max. Pure float arithmetic, no allocation.
            _stormIntensity = Mathf.Min(
                1f + _intensityRampRate * _elapsedTime,
                _maxIntensity
            );

            // ---- Mobile/Desktop Input Sampling (zero alloc) -----------------
            PollInput();

            // ---- Stability Decay / Recovery ---------------------------------
            float decay   = _baseDecayRate * _stormIntensity * Time.deltaTime;
            float counter = _playerCountering ? _counterRate * Time.deltaTime : 0f;

            _boatStability = Mathf.Clamp(
                _boatStability - decay + counter,
                0f,
                _startingStability
            );

            // C# 4.0 compatible null check — no ?. operator allowed.
            if (OnStabilityChanged != null)
                OnStabilityChanged(_boatStability);

            // ---- Wreck Check ------------------------------------------------
            if (_boatStability <= 0f)
                TriggerWreck();
        }

        // =====================================================================
        // Input Polling
        // Input.GetTouch(i) returns a Touch STRUCT by value — stack allocated.
        // This is NOT the same as Input.touches which returns a Touch[] heap array.
        // Zero GC allocation guaranteed.
        // =====================================================================

        private void PollInput()
        {
            _playerCountering = false;

            // ---- Mobile Touch (primary input path) --------------------------
            int touchCount = Input.touchCount; // direct read, no allocation

            for (int i = 0; i < touchCount; i++)
            {
                Touch t = Input.GetTouch(i); // struct by value, stack only

                if (t.phase == TouchPhase.Began     ||
                    t.phase == TouchPhase.Moved      ||
                    t.phase == TouchPhase.Stationary)
                {
                    _playerCountering = true;
                    break; // one active touch is enough — bail early
                }
            }

            // ---- Desktop Keyboard / Mouse Fallback (editor and PC builds) ---
            if (!_playerCountering)
            {
                _playerCountering = Input.GetKey(KeyCode.Space) ||
                                     Input.GetKey(KeyCode.W)     ||
                                     Input.GetMouseButton(0);
            }
        }

        // =====================================================================
        // Public API
        // =====================================================================

        /// <summary>
        /// Starts the storm simulation. In offline mode called automatically
        /// by Start(). In online mode called by BeginStormOnline() after the
        /// countdown completes.
        /// </summary>
        public void BeginStorm()
        {
            if (_state != PrologueState.Idle)
            {
                Debug.LogWarning("[StormPrologue] BeginStorm() called but state is not Idle.");
                return;
            }

            _boatStability  = _startingStability;
            _stormIntensity = 1f;
            _elapsedTime    = 0f;
            _state          = PrologueState.Running;

            Debug.Log("[StormPrologue] Storm has begun. Starting stability: " + _boatStability);
        }

        /// <summary>
        /// Starts the online countdown coroutine and then calls BeginStorm().
        /// Call this when the Unity network client receives the server launch packet.
        /// </summary>
        public void BeginStormOnline()
        {
            if (_state != PrologueState.Idle)
            {
                Debug.LogWarning("[StormPrologue] BeginStormOnline() called but state is not Idle.");
                return;
            }
            StartCoroutine(OnlineCountdownThenStart());
        }

        // =====================================================================
        // Private Helpers
        // =====================================================================

        /// <summary>
        /// Countdown coroutine for online mode. Reuses the pre-allocated
        /// WaitForSeconds to avoid a per-call heap allocation.
        /// </summary>
        private IEnumerator OnlineCountdownThenStart()
        {
            Debug.Log("[StormPrologue] All 15 players connected. Storm starting in " +
                      _onlineCountdownSeconds + "s...");
            yield return _countdownWait; // pre-allocated — zero extra allocation
            BeginStorm();
        }

        /// <summary>
        /// Executes exactly once when stability hits zero.
        /// Transitions internal state, fires events, then delegates scene
        /// change to GameManager for clean separation of concerns.
        /// </summary>
        private void TriggerWreck()
        {
            if (_state == PrologueState.Wrecked) return; // double-trigger guard

            _state         = PrologueState.Wrecked;
            _boatStability = 0f;

            Debug.Log("[StormPrologue] Boat wrecked! Triggering island survival.");
            // C# 4.0 compatible null check — no ?. operator allowed.
            if (OnBoatWrecked != null)
                OnBoatWrecked();
            _gameManager.TriggerIslandSurvival();
        }

        // =====================================================================
        // Editor-Only Debug Helpers
        // =====================================================================

#if UNITY_EDITOR
        [ContextMenu("Debug: Force Wreck Now")]
        private void DebugForceWreck()
        {
            _boatStability = 0f;
            TriggerWreck();
        }

        [ContextMenu("Debug: Begin Storm Now")]
        private void DebugBeginStorm()
        {
            BeginStorm();
        }
#endif
    }
}
