import java.net.URL;
import java.io.InputStream;

public class JavaNetProbe {
    public static void main(String[] args) throws Exception {
        String[] urls = {
            "https://maven.google.com/androidx/core/core-ktx/1.15.0/core-ktx-1.15.0.pom",
            "https://dl.google.com/android/repository/repository2-3.xml",
            "https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/2.0.21/kotlin-stdlib-2.0.21.pom"
        };
        for (String u : urls) {
            try {
                InputStream in = new URL(u).openStream();
                byte[] b = in.readNBytes(64);
                System.out.println("OK   " + u + " -> " + b.length + " bytes");
            } catch (Exception e) {
                System.out.println("FAIL " + u + " -> " + e);
            }
        }
    }
}
