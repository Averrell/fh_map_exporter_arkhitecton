using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Versions;
using Serilog;

namespace Exporter
{
    internal static class Program
    {
        private const EGame  GameVersion = EGame.GAME_UE4_24;
        private const string AesKey      = "0x0000000000000000000000000000000000000000000000000000000000000000";

        static int Main(string[] args)
        {
            Log.Logger = new LoggerConfiguration()
                .MinimumLevel.Information()
                .WriteTo.Console(outputTemplate: "[{Level:u3}] {Message:lj}{NewLine}{Exception}")
                .CreateLogger();

            bool    exportTextures = false;
            string? pakPath        = null;
            string? exportFolder   = null;
            string? assetPath      = null;

            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i].ToLowerInvariant())
                {
                    case "-i" when i + 1 < args.Length:
                        pakPath = args[++i]; break;
                    case "-o" when i + 1 < args.Length:
                        exportFolder = args[++i]; break;
                    case "-a" when i + 1 < args.Length:
                        assetPath = args[++i]; break;
                    case "-t":
                    case "--texture":
                        exportTextures = true; break;
                    default:
                        Console.Error.WriteLine($"Unknown argument: {args[i]}");
                        PrintUsage();
                        return 1;
                }
            }

            if (pakPath == null || exportFolder == null)
            {
                PrintUsage();
                return 1;
            }

            string paksDir;
            if (File.Exists(pakPath))
                paksDir = Path.GetDirectoryName(pakPath)!;
            else if (Directory.Exists(pakPath))
                paksDir = pakPath;
            else
            {
                Log.Error("pak path does not exist: {0}", pakPath);
                return 1;
            }

            Log.Information("Paks directory : {0}", paksDir);
            Log.Information("Export folder  : {0}", exportFolder);
            Log.Information("Texture export : {0}", exportTextures ? "enabled" : "disabled");

            try
            {
                var version  = new VersionContainer(GameVersion);
                var provider = new DefaultFileProvider(paksDir, SearchOption.TopDirectoryOnly,
                                                       version, StringComparer.OrdinalIgnoreCase);
                provider.Initialize();
                provider.SubmitKey(new FGuid(), new FAesKey(AesKey));
                provider.PostMount();

                Log.Information("Provider ready – {0} files indexed", provider.Files.Count);

                var exporter = new MapExporter(provider, exportFolder, exportTextures);

                IEnumerable<string> assetPaths;
                if (assetPath != null)
                {
                    Log.Information("Asset path     : {0}", assetPath);
                    assetPaths = [assetPath];
                }
                else
                {
                    Log.Information("No asset path specified – exporting all umaps under War/Content/Maps");
                    assetPaths = provider.Files.Keys
                        .Where(k => k.StartsWith("War/Content/Maps/", StringComparison.OrdinalIgnoreCase)
                                 && k.EndsWith(".umap", StringComparison.OrdinalIgnoreCase))
                        .OrderBy(k => k, StringComparer.OrdinalIgnoreCase);
                }

                foreach (var ap in assetPaths)
                    exporter.Export(ap);

                Log.Information("Done.");
                return 0;
            }
            catch (Exception ex)
            {
                Log.Fatal(ex, "Unhandled exception");
                return 2;
            }
        }

        private static void PrintUsage()
        {
            Console.Error.WriteLine(
                "Usage: Exporter.exe -i <pak_path> -o <export_path> [-t] [-a <asset_path>]\n" +
                "\n" +
                "  -i <pak_path>     Path to the .pak file or its containing directory\n" +
                "  -o <export_path>  Output folder (meshes/ subdirectory will be created)\n" +
                "  -t, --texture     Also export UTexture2D assets as PNG files\n" +
                "  -a <asset_path>   Asset to export, e.g. War/Content/Maps/HomeRegionC.umap\n" +
                "                    (.umap extension is optional)\n" +
                "                    If omitted, all umaps under War/Content/Maps are exported\n" +
                "                    in alphabetical order\n" +
                "\n" +
                "Examples:\n" +
                "  Exporter.exe -i \"C:\\...\\War-WindowsNoEditor.pak\" -o export -a War/Content/Maps/HomeRegionC\n" +
                "  Exporter.exe -i \"C:\\...\\War-WindowsNoEditor.pak\" -o export -a War/Content/Maps/Master/AcrithiaHex.umap\n" +
                "  Exporter.exe -i \"C:\\...\\Paks\" -o export -t");
        }
    }
}
