using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json.Linq;

namespace Exporter
{
    // Pretty-printed JSON with inline leaf arrays. Dicts and nested arrays use 2-space indent;
    // arrays of only primitives are emitted on one line. Numbers use at most 2 decimal places,
    // whole numbers as "n.0".
    internal static class JsonOutput
    {
        public static string Serialize(JToken token, int indent = 2)
            => Render(token, 0, indent);

        private static bool IsLeafArray(JToken token)
        {
            if (token is not JArray arr) return false;
            foreach (var item in arr)
                if (item.Type == JTokenType.Array || item.Type == JTokenType.Object)
                    return false;
            return true;
        }

        private static string Render(JToken token, int level, int indent)
        {
            var ind     = new string(' ', indent * level);
            var nextInd = new string(' ', indent * (level + 1));

            switch (token)
            {
                case JObject obj:
                {
                    if (!obj.HasValues) return "{}";
                    var sb = new StringBuilder();
                    sb.Append("{\n");
                    var props = new List<string>();
                    foreach (var prop in obj.Properties())
                    {
                        string valStr = IsLeafArray(prop.Value)
                            ? CompactArray((JArray)prop.Value)
                            : Render(prop.Value, level + 1, indent);
                        props.Add($"{nextInd}\"{prop.Name}\": {valStr}");
                    }
                    sb.Append(string.Join(",\n", props));
                    sb.Append($"\n{ind}}}");
                    return sb.ToString();
                }
                case JArray arr:
                {
                    if (IsLeafArray(arr)) return CompactArray(arr);
                    if (!arr.HasValues) return "[]";
                    var parts = new List<string>();
                    foreach (var item in arr)
                        parts.Add($"{nextInd}{Render(item, level + 1, indent)}");
                    return "[\n" + string.Join(",\n", parts) + $"\n{ind}]";
                }
                default:
                    return FormatPrimitive(token);
            }
        }

        private static string CompactArray(JArray arr)
        {
            var parts = new List<string>();
            foreach (var item in arr)
                parts.Add(FormatPrimitive(item));
            return "[" + string.Join(", ", parts) + "]";
        }

        private static string FormatPrimitive(JToken token)
        {
            if (token.Type == JTokenType.Float || token.Type == JTokenType.Integer)
                return FormatDouble((double)token);
            if (token.Type == JTokenType.String) return $"\"{(string)token!}\"";
            if (token.Type == JTokenType.Boolean) return (bool)token ? "true" : "false";
            if (token.Type == JTokenType.Null) return "null";
            return token.ToString();
        }

        // At most 2 decimal places, always at least one digit after the decimal point.
        public static string FormatDouble(double d)
        {
            string s = d.ToString("F2", System.Globalization.CultureInfo.InvariantCulture);
            s = s.TrimEnd('0');
            if (s.EndsWith('.')) s += '0';
            return s;
        }
    }
}
