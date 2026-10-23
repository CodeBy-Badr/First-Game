// =============================================================================
// FILE:     UnityThread.cs
// PATH:     Assets/Scripts/Core/UnityThread.cs
// PURPOSE:  Tiny main-thread dispatcher. Allows background threads (e.g.,
//           network receive loops) to safely schedule Unity API calls.
//           Uses a pre-allocated fixed-capacity action queue to guarantee
//           zero GC allocation per dispatch call during steady-state gameplay.
//
// FIX LOG:
//   - Removed RuntimeInitializeOnLoadMethod auto-create. GameManager now
//     creates UnityThread explicitly in its Awake(), which is safer and
//     avoids double-initialisation in older Unity versions.
//   - Added null guard on _instance inside Dispatch() to prevent NullRef
//     if Dispatch is called before the first scene loads.
//   - Made _mainThreadId initialization happen in the Bootstrap static call
//     so it is captured on the Unity main thread reliably.
// =============================================================================

using System;
using System.Collections.Generic;
using System.Threading;
using UnityEngine;

namespace LostIsland.Core
{
    [DisallowMultipleComponent]
    public sealed class UnityThread : MonoBehaviour
    {
        // =====================================================================
        // Static state — safe to read from any thread
        // =====================================================================

        private static UnityThread _instance;
        private static int _mainThreadId = -1;

        // Pre-allocated double-buffer queues. Capacity 32 covers all 15
        // players with room to spare. Never resized during gameplay.
        private readonly Queue<Action> _pending   = new Queue<Action>(32);
        private readonly Queue<Action> _executing = new Queue<Action>(32);
        private readonly object _queueLock        = new object();

        // =====================================================================
        // Public API
        // =====================================================================

        /// <summary>True when called from the Unity main thread.</summary>
        public static bool IsMainThread
        {
            get { return Thread.CurrentThread.ManagedThreadId == _mainThreadId; }
        }

        /// <summary>
        /// Schedules an action to execute on the next Update() on the
        /// Unity main thread. Zero allocation in steady state.
        /// If called from the main thread, executes the action immediately
        /// to avoid an unnecessary one-frame delay.
        /// </summary>
        public static void Dispatch(Action action)
        {
            if (action == null) return;

            // Already on main thread — run inline, no queue needed.
            if (IsMainThread)
            {
                action();
                return;
            }

            // Guard: if instance not yet created, log and discard.
            if (_instance == null)
            {
                Debug.LogWarning("[UnityThread] Dispatch called before initialization. Action dropped.");
                return;
            }

            lock (_instance._queueLock)
                _instance._pending.Enqueue(action);
        }

        // =====================================================================
        // Bootstrap — called explicitly by GameManager.Awake()
        // =====================================================================

        /// <summary>
        /// Creates the UnityThread singleton. Must be called from the
        /// Unity main thread (e.g., inside GameManager.Awake()).
        /// Safe to call multiple times — only the first call takes effect.
        /// </summary>
        public static void Initialize()
        {
            if (_instance != null) return;

            // Capture the main-thread ID while we are guaranteed to be on it.
            _mainThreadId = Thread.CurrentThread.ManagedThreadId;

            var go = new GameObject("[UnityThread]");
            DontDestroyOnLoad(go);
            _instance = go.AddComponent<UnityThread>();
        }

        // =====================================================================
        // Unity Lifecycle
        // =====================================================================

        private void Awake()
        {
            // Destroy duplicates (e.g., if a second scene also calls Initialize).
            if (_instance != null && _instance != this)
            {
                Destroy(gameObject);
                return;
            }
            _instance = this;
        }

        private void OnDestroy()
        {
            if (_instance == this)
                _instance = null;
        }

        private void Update()
        {
            // Early-out avoids acquiring the lock when there is nothing to do.
            if (_pending.Count == 0) return;

            // Swap queues under the lock — the lock is held only for the
            // duration of the O(n) dequeue, NOT during action execution.
            lock (_queueLock)
            {
                while (_pending.Count > 0)
                    _executing.Enqueue(_pending.Dequeue());
            }

            // Execute outside the lock so background threads can continue
            // enqueuing while we drain the executing queue on the main thread.
            while (_executing.Count > 0)
            {
                Action action = _executing.Dequeue();
                try
                {
                    action();
                }
                catch (Exception ex)
                {
                    Debug.LogError("[UnityThread] Dispatched action threw: " + ex.Message);
                }
            }
        }
    }
}
