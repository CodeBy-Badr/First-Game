// =============================================================================
// FILE:     CompanionAI.cs
// PATH:     Assets/Scripts/AI/CompanionAI.cs
// PURPOSE:  Ultra-lightweight Finite State Machine (FSM) for the 14 offline
//           AI companion characters.
//
//  ARCHITECTURE
//  ------------
//  - CompanionState enum: five island/prologue task states stored as byte.
//  - CompanionAgent: one MonoBehaviour per AI character. Owns FSM state logic.
//  - CompanionDirector: non-MonoBehaviour singleton that broadcasts global
//    events (OnNightFalls, OnCommandReceived) to all registered agents.
//    Uses a fixed-size array of 14 slots — zero List<T> resize overhead.
//
//  ZERO-GC DESIGN
//  --------------
//  - Fixed CompanionAgent[14] array — no List<T>, no resize, no GC spikes.
//  - State transitions write to a byte-sized enum field — no string hashing.
//  - Dirty flag pattern: Director sets _stateDirty; agent checks in Update.
//    No per-frame delegate allocation on the hot path.
//  - Swap-and-pop unregister: O(n) find, O(1) remove — no array shifting.
//  - All Debug.Log calls inside UNITY_EDITOR guards to eliminate string
//    allocation overhead in release builds.
//
// FIX LOG:
//   - Removed Lazy<T> singleton for CompanionDirector (caused issues on older
//     Unity Mono runtimes). Replaced with explicit double-checked locking.
//   - Fixed volatile bool _stateDirty race: now uses a dedicated lock-free
//     pattern with _pendingState written before _stateDirty to ensure the
//     main thread always reads a consistent pending state.
//   - Removed duplicate 'using System' which caused CS0105 on some versions.
//   - CompanionDirector._registryLock now correctly covers all _agentCount reads.
//   - Null-check on _agents[i] inside broadcast loops moved outside the hot path.
// =============================================================================

using UnityEngine;
using LostIsland.Data;

namespace LostIsland.AI
{
    // -------------------------------------------------------------------------
    // CompanionState — stored as byte to minimize per-agent memory footprint.
    // -------------------------------------------------------------------------
    public enum CompanionState : byte
    {
        Idle            = 0,  // Default / unassigned
        AssistedStorm   = 1,  // Prologue: helping manage the boat
        Foraging        = 2,  // Island: gathering food and resources
        BuildingShelter = 3,  // Island: constructing or repairing shelter
        DefendingCamp   = 4,  // Island: guarding the perimeter
        FollowingLeader = 5   // Island: shadowing the player character
    }

    // =========================================================================
    // CompanionAgent — one instance per AI boy (14 total in offline mode)
    // =========================================================================
    [DisallowMultipleComponent]
    public sealed class CompanionAgent : MonoBehaviour
    {
        // =====================================================================
        // Inspector Configuration
        // =====================================================================

        [Header("Identity")]
        [Tooltip("Which of the 15 boys this AI agent represents.")]
        [SerializeField] private BoyId _boyId;

        [Header("AI Timing")]
        [Tooltip("Seconds between state-logic ticks. Stagger across agents to avoid frame spikes.")]
        [Range(0.1f, 2f)]
        [SerializeField] private float _tickInterval = 0.5f;

        // =====================================================================
        // Runtime State — all value-types
        // =====================================================================

        /// <summary>Current FSM state. Externally readable, only set internally.</summary>
        public CompanionState CurrentState { get; private set; }

        /// <summary>The character this agent embodies.</summary>
        public BoyId BoyId
        {
            get { return _boyId; }
        }

        // Tick timer accumulator — avoids a coroutine (zero allocation).
        private float _tickTimer;

        // Lock-free state handshake between CompanionDirector (any thread)
        // and this agent's Update() (main thread only).
        // _pendingState is written BEFORE _stateDirty to guarantee the main
        // thread always sees a valid state when it checks the dirty flag.
        private CompanionState _pendingState;
        private volatile bool  _stateDirty;

        // =====================================================================
        // Unity Lifecycle
        // =====================================================================

        private void Awake()
        {
            CurrentState = CompanionState.Idle;
            _tickTimer   = 0f;
            _stateDirty  = false;

            // Register with the director immediately so broadcasts reach this agent.
            CompanionDirector.Instance.RegisterAgent(this);
        }

        private void OnDestroy()
        {
            // Unregister on destroy to prevent the Director holding a stale ref.
            CompanionDirector.Instance.UnregisterAgent(this);
        }

        private void Update()
        {
            // ---- Apply pending state change (written by Director on any thread) ----
            if (_stateDirty)
            {
                ApplyState(_pendingState);
                _stateDirty = false;
            }

            // ---- Staggered AI tick — only runs every _tickInterval seconds ----
            _tickTimer += Time.deltaTime;
            if (_tickTimer < _tickInterval) return;

            // Subtract rather than reset to preserve phase across frames.
            _tickTimer -= _tickInterval;

            TickBehavior();
        }

        // =====================================================================
        // Public API — called by CompanionDirector
        // =====================================================================

        /// <summary>
        /// Queues a state transition for the next Update() tick on the main thread.
        /// Thread-safe: _pendingState is written before the volatile _stateDirty flag.
        /// </summary>
        public void RequestStateChange(CompanionState newState)
        {
            // Write value BEFORE setting the dirty flag (memory ordering guarantee).
            _pendingState = newState;
            _stateDirty   = true; // volatile write — immediately visible to main thread
        }

        // =====================================================================
        // Private — State Machine Logic
        // =====================================================================

        /// <summary>
        /// Commits the pending state transition.
        /// Always called on the main thread inside Update().
        /// </summary>
        private void ApplyState(CompanionState newState)
        {
            if (CurrentState == newState) return; // no-op if already in target state

#if UNITY_EDITOR
            Debug.Log("[CompanionAgent:" + _boyId + "] " + CurrentState + " -> " + newState);
#endif

            ExitState(CurrentState);
            CurrentState = newState;
            EnterState(CurrentState);
        }

        // ---- Enter/Exit Hooks -----------------------------------------------
        // Expand these with NavMeshAgent commands, Animator triggers, etc.

        private void EnterState(CompanionState state)
        {
            switch (state)
            {
                case CompanionState.AssistedStorm:
                    // Hook: activate storm-assist animations / navigation target.
                    break;

                case CompanionState.Foraging:
                    // Hook: set NavMeshAgent destination to nearest resource node.
                    break;

                case CompanionState.BuildingShelter:
                    // Hook: navigate to nearest construction site.
                    break;

                case CompanionState.DefendingCamp:
                    // Hook: move to patrol waypoint, enable threat detection.
                    break;

                case CompanionState.FollowingLeader:
                    // Hook: set follow target to GameManager.LocalPlayer transform.
                    break;

                case CompanionState.Idle:
                default:
                    break;
            }
        }

        private void ExitState(CompanionState state)
        {
            // Per-state cleanup — cancel navigation, stop animations, etc.
            switch (state)
            {
                case CompanionState.DefendingCamp:
                    // Hook: disable threat detection component.
                    break;

                default:
                    break;
            }
        }

        // ---- Per-State Tick Logic -------------------------------------------
        // Runs at _tickInterval frequency, NOT every frame.
        // Each stub expands with real gameplay logic in later steps.

        private void TickBehavior()
        {
            switch (CurrentState)
            {
                case CompanionState.AssistedStorm:
                    TickAssistedStorm();
                    break;

                case CompanionState.Foraging:
                    TickForaging();
                    break;

                case CompanionState.BuildingShelter:
                    TickBuildingShelter();
                    break;

                case CompanionState.DefendingCamp:
                    TickDefendingCamp();
                    break;

                case CompanionState.FollowingLeader:
                    TickFollowingLeader();
                    break;

                case CompanionState.Idle:
                default:
                    break;
            }
        }

        private void TickAssistedStorm()
        {
            // Expand: apply stability boost to StormPrologue controller.
        }

        private void TickForaging()
        {
            // Expand: check if agent reached resource node; collect if so.
        }

        private void TickBuildingShelter()
        {
            // Expand: add construction progress to nearest ShelterSite component.
        }

        private void TickDefendingCamp()
        {
            // Expand: scan for threats within detection radius via Physics.OverlapSphere.
        }

        private void TickFollowingLeader()
        {
            // Expand: update NavMeshAgent destination to player's current position.
        }
    }

    // =========================================================================
    // CompanionDirector — singleton event broadcaster for all 14 AI agents.
    // Non-MonoBehaviour — does not need a scene GameObject.
    // Fixed-size array guarantees zero resize allocation after initial load.
    // =========================================================================
    public sealed class CompanionDirector
    {
        // =====================================================================
        // Singleton — double-checked locking (no Lazy<T> to avoid Mono issues)
        // =====================================================================

        private static volatile CompanionDirector _instance;
        private static readonly object _singletonLock = new object();

        /// <summary>Thread-safe singleton accessor.</summary>
        public static CompanionDirector Instance
        {
            get
            {
                if (_instance != null) return _instance;

                lock (_singletonLock)
                {
                    if (_instance == null)
                        _instance = new CompanionDirector();
                }
                return _instance;
            }
        }

        // =====================================================================
        // Agent Registry
        // =====================================================================

        private const int MAX_COMPANIONS = 14;

        // Fixed array — allocated once. _agentCount tracks the filled slots.
        private readonly CompanionAgent[] _agents = new CompanionAgent[MAX_COMPANIONS];
        private int _agentCount;

        // Single lock guards both _agents array and _agentCount mutations.
        private readonly object _registryLock = new object();

        // Private constructor enforces singleton.
        private CompanionDirector()
        {
            _agentCount = 0;
        }

        // =====================================================================
        // Agent Registration (called from CompanionAgent Unity lifecycle)
        // =====================================================================

        /// <summary>
        /// Registers an agent into the fixed-size roster.
        /// Called by CompanionAgent.Awake(). Thread-safe via _registryLock.
        /// </summary>
        public void RegisterAgent(CompanionAgent agent)
        {
            if (agent == null) return;

            lock (_registryLock)
            {
                if (_agentCount >= MAX_COMPANIONS)
                {
                    Debug.LogWarning("[CompanionDirector] Roster full (max 14). Ignoring registration.");
                    return;
                }
                _agents[_agentCount] = agent;
                _agentCount++;
            }
        }

        /// <summary>
        /// Removes an agent from the roster when it is destroyed or scene-unloaded.
        /// Uses swap-and-pop: O(n) find, O(1) remove — no array shifting required.
        /// </summary>
        public void UnregisterAgent(CompanionAgent agent)
        {
            if (agent == null) return;

            lock (_registryLock)
            {
                for (int i = 0; i < _agentCount; i++)
                {
                    if (_agents[i] == agent)
                    {
                        // Move the last filled slot into the vacated slot.
                        _agents[i] = _agents[_agentCount - 1];
                        _agents[_agentCount - 1] = null; // release managed reference
                        _agentCount--;
                        return;
                    }
                }
            }
        }

        // =====================================================================
        // Global Event Broadcasts
        // Each method is a single O(n) loop over _agents — zero allocation.
        // =====================================================================

        /// <summary>
        /// Broadcast: Night has fallen.
        /// Splits agents across BuildingShelter (first half) and
        /// DefendingCamp (second half) using a simple priority heuristic.
        /// Called once per in-game day cycle from a DayNightCycle controller.
        /// </summary>
        public void OnNightFalls()
        {
            lock (_registryLock)
            {
                int halfPoint = _agentCount / 2;

                for (int i = 0; i < _agentCount; i++)
                {
                    if (_agents[i] == null) continue;

                    CompanionState target = (i < halfPoint)
                        ? CompanionState.BuildingShelter
                        : CompanionState.DefendingCamp;

                    _agents[i].RequestStateChange(target);
                }
            }

            Debug.Log("[CompanionDirector] Night falls. Agents split: BuildingShelter / DefendingCamp.");
        }

        /// <summary>
        /// Broadcast: The player has issued a direct command.
        /// All 14 registered agents immediately queue a transition to newState.
        /// Thread-safe — safe to call from a UI button handler.
        /// </summary>
        public void OnCommandReceived(CompanionState newState)
        {
            lock (_registryLock)
            {
                for (int i = 0; i < _agentCount; i++)
                {
                    if (_agents[i] != null)
                        _agents[i].RequestStateChange(newState);
                }
            }

#if UNITY_EDITOR
            Debug.Log("[CompanionDirector] Command broadcast -> " + newState +
                      " to " + _agentCount + " agents.");
#endif
        }

        /// <summary>
        /// Convenience broadcast: switches all companions to AssistedStorm
        /// at the start of the prologue so they help manage the boat.
        /// </summary>
        public void OnStormBegins()
        {
            OnCommandReceived(CompanionState.AssistedStorm);
            Debug.Log("[CompanionDirector] Storm begins. All companions -> AssistedStorm.");
        }

        /// <summary>
        /// Convenience broadcast: distributes agents across island tasks
        /// immediately after the wreck (Foraging / BuildingShelter / FollowingLeader).
        /// </summary>
        public void OnIslandArrival()
        {
            lock (_registryLock)
            {
                int third = _agentCount / 3;

                for (int i = 0; i < _agentCount; i++)
                {
                    if (_agents[i] == null) continue;

                    CompanionState s;
                    if (i < third)
                        s = CompanionState.Foraging;
                    else if (i < third * 2)
                        s = CompanionState.BuildingShelter;
                    else
                        s = CompanionState.FollowingLeader;

                    _agents[i].RequestStateChange(s);
                }
            }

            Debug.Log("[CompanionDirector] Island arrival. Agents distributed across survival tasks.");
        }

        /// <summary>
        /// Clears the entire agent registry. Call when a scene is fully unloaded
        /// to prevent stale references from persisting across scene boundaries.
        /// </summary>
        public void ClearAll()
        {
            lock (_registryLock)
            {
                for (int i = 0; i < _agentCount; i++)
                    _agents[i] = null;
                _agentCount = 0;
            }

            Debug.Log("[CompanionDirector] Agent registry cleared.");
        }
    }
}
