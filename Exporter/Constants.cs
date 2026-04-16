using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace Exporter
{
    internal static class Constants
    {
        /// <summary>Maps "destroyed" blueprint paths → replacement blueprint paths.</summary>
        public static readonly Dictionary<string, string> Patches = new()
        {
            ["War/Content/Blueprints/Structures/Bases/BPDestroyedRelicBase1"] = "War/Content/Blueprints/Structures/Bases/BPRelicBase1",
            ["War/Content/Blueprints/Structures/Bases/BPDestroyedRelicBase2"] = "War/Content/Blueprints/Structures/Bases/BPRelicBase2",
            ["War/Content/Blueprints/Structures/Bases/BPDestroyedRelicBase3"] = "War/Content/Blueprints/Structures/Bases/BPRelicBase3",
            ["War/Content/Blueprints/Structures/BPDestroyedKeep"]             = "War/Content/Blueprints/Structures/BPKeep",
            ["War/Content/Blueprints/Structures/BPDestroyedObservationTower"] = "War/Content/Blueprints/Structures/BPObservationTower",
        };

        /// <summary>Component ExportTypes that are always skipped.</summary>
        public static readonly HashSet<string> SkipTypes = new(System.StringComparer.OrdinalIgnoreCase)
        {
            "DecalComponent",
            "SplineComponent",
            "SplineMeshComponent",
        };

        public static string NormaliseMeshName(string meshName)
        {
            if (meshName == "Meshes__Structures__ConstructionYardCritical")
                return "Meshes__Structures__ConstructionYard";
            if (meshName == "Meshes__Structures__FortTrenches__AIBunkers__husks__FortT3WallBreach")
                return "Meshes__Structures__FortTrenches__FortT3Wall01";
            return meshName;
        }

        public static string NormaliseBPName(string bpName)
        {
            if (bpName == "BPConcreteBridgeNoBlocker_C")
                return "BPConcreteBridge_C";
            return bpName;
        }

        private static readonly string[] _patternStrings =
        {
            "Engine__Content__BasicShapes__.*",
            "Meshes__Measurement__Plane",
            "FX__Mesh__.*",
            "Meshes__SM_SkySphere",
            "Meshes__Vehicles__BargeDestroyed",
            "Meshes__Vehicles__CraneDestroyed",
            "Meshes__Vehicles__Freighter02Destroyed",
            "Meshes__Vehicles__Freighter02ShipCollision",
            "Meshes__Vehicles__HarvesterDestroyed",
            "Meshes__Vehicles__Headlight",
            "Meshes__Vehicles__MotorboatDestroyed",
            "Meshes__Vehicles__Motorboat_cull",
            "Meshes__Vehicles__SM_ScoutVehicleBaseC",
            "Meshes__Vehicles__SM_ScoutVehicleBaseW",
            "Meshes__Vehicles__SM_TruckBaseW",
            "Meshes__Vehicles__SM_TruckBaseW_Trailer",
            "Meshes__Vehicles__SM_TruckBaseC",
            "Meshes__Vehicles__SM_TruckBaseC_Trailer",
            "Meshes__Shippables__ShippingContainerLargeExposed",
            "Meshes__Vehicles__SK_Crane",
            "Meshes__Vehicles__SK_Barge_03",
            "Meshes__Vehicles__SK_FlatbedTruck",
            "Meshes__Vehicles__SK_ScoutVehicleBaseW_Cabin",
            "Meshes__Structures__SK_RailTrackSwitch"
        };

        private static readonly Regex[] _hardbanPatterns =
            System.Array.ConvertAll(_patternStrings, p => new Regex(p, RegexOptions.IgnoreCase | RegexOptions.Compiled));

        public static bool IsHardbanned(string unpathName)
        {
            foreach (var rx in _hardbanPatterns)
                if (rx.IsMatch(unpathName)) return true;
            return false;
        }
    }
}
