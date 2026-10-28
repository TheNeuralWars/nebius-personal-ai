// ZetarisJdbcQuery.java — tiny JDBC helper for the Zetaris Lightning driver.
//
// Runs ONE read-only SQL statement over jdbc:zetaris:lightning@host:port and prints
// the result as JSON on stdout: {"columns": [...], "rows": [{col: value, ...}]}.
//
// Single-file source: run it directly with a JDK 11+ (no build step):
//   java tools/ZetarisJdbcQuery.java --url jdbc:zetaris:lightning@localhost:10000 \
//        --jar /path/to/ndp-jdbc-driver-*.jar --class com.zetaris.lightning.jdbc.LightningDriver \
//        --user admin@zetaris.com --sql "SELECT 1 AS ok"   < password-file
//
// The password arrives on STDIN (one line), never argv or logs. The driver jar is a
// licensed artefact: keep it outside the repository (see .gitignore, *.jar).
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Paths;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class ZetarisJdbcQuery {
    public static void main(String[] args) throws Exception {
        Map<String, String> opt = parseArgs(args);
        require(opt, "--url");
        require(opt, "--jar");
        require(opt, "--class");
        require(opt, "--user");
        require(opt, "--sql");

        // Read-only guard: this helper is a query tool, nothing else.
        String sql = opt.get("--sql").trim();
        String head = sql.toLowerCase();
        if (!(head.startsWith("select") || head.startsWith("with"))) {
            fail("only SELECT/WITH statements are allowed");
        }

        String password;
        try (BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            password = in.readLine();
        }
        if (password == null) {
            fail("expected the password on stdin");
            return;
        }

        String jar = Paths.get(opt.get("--jar")).toAbsolutePath().toString();
        ClassLoader parent = ZetarisJdbcQuery.class.getClassLoader();
        java.net.URLClassLoader loader = new java.net.URLClassLoader(
                new java.net.URL[]{Paths.get(jar).toUri().toURL()}, parent);
        Class<?> driverClass = Class.forName(opt.get("--class"), true, loader);

        // Instantiate the driver directly instead of DriverManager.getConnection:
        // DriverManager silently skips drivers whose class is not visible to the
        // caller's classloader, and ours lives in the child URLClassLoader.
        java.sql.Driver driver = (java.sql.Driver) driverClass.getDeclaredConstructor().newInstance();
        java.util.Properties props = new java.util.Properties();
        props.setProperty("user", opt.get("--user"));
        props.setProperty("password", password);

        StringBuilder out = new StringBuilder();
        try (Connection conn = driver.connect(opt.get("--url"), props)) {
            if (conn == null) {
                fail("the driver refused the URL (wrong --url or --class?)");
                return;
            }
            try (Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery(sql)) {
            ResultSetMetaData md = rs.getMetaData();
            int n = md.getColumnCount();
            List<String> columns = new ArrayList<>();
            for (int i = 1; i <= n; i++) {
                columns.add(md.getColumnLabel(i));
            }
            out.append("{\"columns\": [");
            for (int i = 0; i < n; i++) {
                if (i > 0) out.append(", ");
                out.append(jsonString(columns.get(i)));
            }
            out.append("], \"rows\": [");
            long rows = 0;
            while (rs.next()) {
                if (rows++ > 0) out.append(", ");
                out.append("{");
                for (int i = 1; i <= n; i++) {
                    if (i > 1) out.append(", ");
                    Object v = rs.getObject(i);
                    out.append(jsonString(columns.get(i - 1))).append(": ").append(jsonValue(v));
                }
                out.append("}");
            }
            out.append("]}");
            }
        }
        System.out.println(out);
    }

    static Map<String, String> parseArgs(String[] args) {
        Map<String, String> opt = new LinkedHashMap<>();
        for (int i = 0; i + 1 < args.length; i += 2) {
            if (args[i].startsWith("--")) {
                opt.put(args[i], args[i + 1]);
            }
        }
        return opt;
    }

    static void require(Map<String, String> opt, String key) {
        if (!opt.containsKey(key)) {
            fail("missing argument " + key);
        }
    }

    static void fail(String message) {
        System.err.println("ZetarisJdbcQuery: " + message);
        System.exit(2);
    }

    static String jsonValue(Object v) {
        if (v == null) return "null";
        if (v instanceof Number || v instanceof Boolean) return v.toString();
        return jsonString(v.toString());
    }

    static String jsonString(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append('"').toString();
    }
}
