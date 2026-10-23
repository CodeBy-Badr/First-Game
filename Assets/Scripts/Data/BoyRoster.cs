// =============================================================================
// FILE:     BoyRoster.cs
// PATH:     Assets/Scripts/Data/BoyRoster.cs
// PURPOSE:  Canonical 15-boy roster and PlayerProfile value-type.
//           Pure data layer — no MonoBehaviour, no Unity lifecycle,
//           zero heap allocation beyond the one-time static array init.
//           Mobile-safe: all lookups are O(1), no LINQ, no boxing.
// =============================================================================

using System;

namespace LostIsland.Data
{
    // -------------------------------------------------------------------------
    // BoyId — enum ordinal doubles as the lobby slot index (0-14).
    // Stored as byte to minimize struct padding in PlayerProfile.
    // -------------------------------------------------------------------------
    public enum BoyId : byte
    {
        Gordon   = 0,
        Prim     = 1,
        Doniphan = 2,
        Baxter   = 3,
        Cross    = 4,
        Webb     = 5,
        Wilcox   = 6,
        Service  = 7,
        Garnett  = 8,
        Jack     = 9,
        Jenkins  = 10,
        Iverson  = 11,
        Dole     = 12,
        Costar   = 13,
        Moko     = 14
    }

    // -------------------------------------------------------------------------
    // BoyRoster — static read-only roster table.
    // Allocated once at domain init; never resized, never boxed.
    // -------------------------------------------------------------------------
    public static class BoyRoster
    {
        public const int ROSTER_SIZE = 15;

        // Indexed by BoyId ordinal — O(1) name lookup, no dictionary overhead.
        private static readonly string[] _names = new string[ROSTER_SIZE]
        {
            "Gordon",    // 0
            "Prim",      // 1
            "Doniphan",  // 2
            "Baxter",    // 3
            "Cross",     // 4
            "Webb",      // 5
            "Wilcox",    // 6
            "Service",   // 7
            "Garnett",   // 8
            "Jack",      // 9
            "Jenkins",   // 10
            "Iverson",   // 11
            "Dole",      // 12
            "Costar",    // 13
            "Moko"       // 14
        };

        /// <summary>Returns display name for a BoyId. Zero allocation. O(1).</summary>
        public static string GetName(BoyId id)
        {
            return _names[(int)id];
        }

        /// <summary>Returns display name by slot index. O(1).</summary>
        public static string GetName(int index)
        {
            return _names[index];
        }

        /// <summary>
        /// Validates a raw slot index without branching on negative values.
        /// Unsigned cast collapses the negative-number case to a large uint,
        /// which is always >= ROSTER_SIZE, one comparison handles both bounds.
        /// </summary>
        public static bool IsValidIndex(int index)
        {
            return (uint)index < (uint)ROSTER_SIZE;
        }
    }

    // -------------------------------------------------------------------------
    // PlayerProfile — blittable struct (value-type) to eliminate GC pressure.
    // Pass by ref where mutation is needed; copied cheaply where immutable.
    // SessionId is a Guid (16 bytes), DisplayName is the only managed ref field.
    // -------------------------------------------------------------------------
    [Serializable]
    public struct PlayerProfile
    {
        /// <summary>Unique per-session GUID assigned at login or session start.</summary>
        public Guid   SessionId;

        /// <summary>Human-readable name (defaults to character name in offline mode).</summary>
        public string DisplayName;

        /// <summary>Character locked for this session. Byte-sized enum — minimal padding.</summary>
        public BoyId  SelectedBoy;

        /// <summary>True when playing in offline single-player mode.</summary>
        public bool   IsOffline;

        // ---- Factory helpers ------------------------------------------------

        /// <summary>Creates an offline profile for the chosen character.</summary>
        public static PlayerProfile CreateOffline(BoyId boy)
        {
            return new PlayerProfile
            {
                SessionId   = Guid.NewGuid(),
                DisplayName = BoyRoster.GetName(boy),
                SelectedBoy = boy,
                IsOffline   = true
            };
        }

        /// <summary>Creates an online profile with a server-assigned session id.</summary>
        public static PlayerProfile CreateOnline(Guid sessionId, string displayName, BoyId boy)
        {
            return new PlayerProfile
            {
                SessionId   = sessionId,
                DisplayName = displayName,
                SelectedBoy = boy,
                IsOffline   = false
            };
        }

        // FIX: Removed nested quotes inside interpolated string that caused CS1010.
        // Use a pre-built mode string instead of a ternary inside $"".
        public override string ToString()
        {
            string mode = IsOffline ? "OFFLINE" : "ONLINE";
            return "[" + mode + "] " + DisplayName + " (" + SelectedBoy + ") - " + SessionId;
        }
    }
}
