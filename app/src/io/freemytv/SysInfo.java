package io.freemytv;

import android.app.ActivityManager;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.TrafficStats;
import android.net.wifi.WifiInfo;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Environment;
import android.os.StatFs;
import android.os.SystemClock;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.Locale;

/**
 * What the TV is doing right now, for the corner capsule and the drawer's card: the frame rate the home screen is
 * actually drawing at, the CPU load (and its last minute, for the card's line), the memory the TV has and uses, the
 * storage it has left, the network's speed, and the Wi-Fi network it is on.
 *
 * Everything here is read on the drawing thread and must stay cheap: /proc/stat and /proc/meminfo are a few hundred
 * bytes, and the SSID is cached for a minute (asking the Wi-Fi service costs a binder call). Nothing is fetched from
 * the network, so this works offline, unlike the prices it replaces.
 */
final class SysInfo {
    private SysInfo() {}

    // MARK: - Frames per second

    /** Frames drawn in the last second, as the home screen's own frame callback counted them. */
    private static volatile float fps = 60;

    /** Called once per frame by HomeView: the frames in the last second, smoothed so the number doesn't flicker. */
    static void frame(long now) {
        // A callback a few milliseconds after the one before it is the same screen frame delivered again (the
        // Choreographer does that for callbacks posted with a delay): a TV never draws two frames that close.
        if (now - lastFrameAt < 6) return;
        lastFrameAt = now;
        frames++;
        if (windowStart == 0) windowStart = now;
        long span = now - windowStart;
        if (span < 1000) return;
        float measured = frames * 1000f / span;
        // A screen that sat still (the callback runs once a second when nothing moves) isn't drawing at 1 fps: keep
        // the last real reading instead of dropping to it.
        if (measured >= 5) fps = fps * 0.5f + measured * 0.5f;
        frames = 0;
        windowStart = now;
    }

    private static int frames;
    private static long windowStart, lastFrameAt;

    static int fps() {
        return Math.round(fps);
    }

    // MARK: - CPU

    private static long lastCpuTicks = -1, lastCpuAt;
    private static volatile float cpu = 0;
    private static volatile boolean cpuUnreadable;
    private static long tickAt;

    /**
     * Once a second, from the frame callback: the CPU's load, which the pill shows and the card keeps as a line. Read
     * here and not where it's drawn: two reads a frame apart would measure nothing.
     */
    static void tick(long now) {
        if (tickAt != 0 && now - tickAt < 1000) return;
        long span = tickAt == 0 ? 0 : now - tickAt;
        tickAt = now;
        sampleCpu();
        sampleTraffic(span);
    }

    /**
     * The home screen's own CPU load since the last call, as a percentage of the whole chip (so one busy core on a
     * four-core TV reads 25%, as Task Manager would show it).
     *
     * /proc/stat, the whole TV's load, is refused to apps on Android 11 (SELinux labels it proc_stat: only the shell and
     * the system may read it), so this reads /proc/self/stat instead: the process always may read its own. It pairs
     * with the pill's memory figure, which is the app's own too.
     */
    static void sampleCpu() {
        long now = SystemClock.elapsedRealtime();
        try (BufferedReader in = new BufferedReader(new FileReader("/proc/self/stat"), 512)) {
            String line = in.readLine();
            if (line == null) throw new IllegalStateException("empty");
            // The command name is in parentheses and may hold spaces: the fields after it start at the last ')'.
            int close = line.lastIndexOf(')');
            if (close < 0) throw new IllegalStateException("no command name");
            String[] f = line.substring(close + 2).trim().split("\\s+");
            // After the command name, field 3 is state: utime is the 14th field of the line, so index 11 here.
            long ticks = Long.parseLong(f[11]) + Long.parseLong(f[12]);   // utime + stime, in 100 Hz ticks
            if (lastCpuTicks >= 0 && now > lastCpuAt) {
                float seconds = (now - lastCpuAt) / 1000f;
                float load = 100f * ((ticks - lastCpuTicks) / 100f) / seconds / cores();
                cpu = Math.max(0, Math.min(100, load));
                record(cpu);
            }
            lastCpuTicks = ticks;
            lastCpuAt = now;
            cpuUnreadable = false;
        } catch (Exception e) {
            if (!cpuUnreadable) AppLog.w("cpu: /proc/self/stat unreadable: " + e);
            cpuUnreadable = true;
        }
    }

    /** The CPU's load over the last minute, oldest first: what the card draws as a line. */
    static final int HISTORY = 60;
    private static final float[] history = new float[HISTORY];
    private static int historyCount, historyNext;
    private static float historySum;

    private static void record(float load) {
        if (historyCount == HISTORY) historySum -= history[historyNext];
        else historyCount++;
        history[historyNext] = load;
        historySum += load;
        historyNext = (historyNext + 1) % HISTORY;
    }

    /** Copies the history (oldest first) into `out`; returns how many values it holds (0 before the second reading). */
    static int history(float[] out) {
        int n = Math.min(historyCount, out.length), start = (historyNext - n + HISTORY) % HISTORY;
        for (int i = 0; i < n; i++) out[i] = history[(start + i) % HISTORY];
        return n;
    }

    /** The CPU's load over the last minute in percent, for the figure under the card's big one. */
    static int cpuAverage() {
        return historyCount == 0 ? cpu() : Math.round(historySum / historyCount);
    }

    private static int coreCount;

    /** How many cores the TV has (4 on most), so a process's load can be read as a share of the whole chip. */
    private static int cores() {
        if (coreCount > 0) return coreCount;
        int n = Runtime.getRuntime().availableProcessors();
        coreCount = n > 0 ? n : 1;
        return coreCount;
    }

    /** The home screen's CPU load in percent, or -1 when it can't be read. */
    static int cpu() {
        return cpuUnreadable ? -1 : Math.round(cpu);
    }

    // MARK: - Memory

    /** The app's own resident memory in MB (what the home screen actually costs), or -1 if unreadable. */
    static int ramMb() {
        // The Java heap's total is the app's own footprint and needs no permission; the RSS in /proc/self/statm is the
        // honest figure (the heap alone leaves out the bitmaps and the native side), so prefer it.
        try (BufferedReader in = new BufferedReader(new FileReader("/proc/self/statm"), 128)) {
            String line = in.readLine();
            if (line != null) {
                String[] f = line.trim().split("\\s+");
                if (f.length > 1) {
                    long pages = Long.parseLong(f[1]);
                    long kb = pages * 4;   // Android runs a 4 KB page size on every TV chip we've seen
                    if (kb > 0) return (int) Math.round(kb / 1024.0);
                }
            }
        } catch (Exception ignored) {
        }
        Runtime rt = Runtime.getRuntime();
        long used = rt.totalMemory() - rt.freeMemory();
        return used > 0 ? (int) Math.round(used / (1024.0 * 1024.0)) : -1;
    }

    // MARK: - What the TV has: its memory, its storage and the network's speed

    private static final ActivityManager.MemoryInfo MEM = new ActivityManager.MemoryInfo();
    private static long tvAt;
    private static int memTotal = -1, memUsed = -1;
    private static long storageFree = -1, storageTotal = -1;

    /**
     * The TV's memory (in use and in total) and the storage it has left, for the performance card. Read at most once a
     * second and only while that card draws: the first two ask the system service, a binder call, and the card is
     * redrawn on every frame of the drawer's animation.
     */
    static void sampleTv(Context c) {
        long now = SystemClock.uptimeMillis();
        if (tvAt != 0 && now - tvAt < 1000) return;
        tvAt = now;
        try {
            ActivityManager am = c.getSystemService(ActivityManager.class);
            if (am != null) {
                am.getMemoryInfo(MEM);
                memTotal = (int) (MEM.totalMem / (1024 * 1024));
                memUsed = (int) ((MEM.totalMem - MEM.availMem) / (1024 * 1024));
            }
        } catch (Exception e) {
            memTotal = memUsed = -1;
        }
        try {
            StatFs fs = new StatFs(Environment.getDataDirectory().getPath());
            storageFree = fs.getAvailableBytes() / (1024 * 1024);
            storageTotal = fs.getTotalBytes() / (1024 * 1024);
        } catch (Exception e) {
            storageFree = storageTotal = -1;
        }
    }

    /** The TV's own memory in MB, or -1 when unreadable. */
    static int memTotalMb() {
        return memTotal;
    }

    /** The TV's memory in use in MB, all apps included (not just this one), or -1 when unreadable. */
    static int memUsedMb() {
        return memUsed;
    }

    /** The storage left for apps and photos in MB, or -1 when unreadable. */
    static long storageFreeMb() {
        return storageFree;
    }

    static long storageTotalMb() {
        return storageTotal;
    }

    private static long rx = -1, tx = -1;
    private static float down = -1, up = -1;    // MB/s, since the last tick

    /** The network's speed from the counters Android keeps: what came in and what went out since the last tick. */
    private static void sampleTraffic(long spanMs) {
        long r = TrafficStats.getTotalRxBytes(), t = TrafficStats.getTotalTxBytes();
        if (r < 0 || t < 0) {    // some firmware doesn't count it (TrafficStats.UNSUPPORTED)
            rx = tx = -1;
            down = up = -1;
            return;
        }
        if (rx >= 0 && tx >= 0 && spanMs > 0) {
            down = (r - rx) / 1048576f / (spanMs / 1000f);
            up = (t - tx) / 1048576f / (spanMs / 1000f);
        }
        rx = r;
        tx = t;
    }

    /** What the TV received over the last second, in MB/s (-1 when unreadable and at the first reading). */
    static float downMbs() {
        return down;
    }

    /** What the TV sent over the last second, in MB/s. */
    static float upMbs() {
        return up;
    }

    // MARK: - Wi-Fi

    private static String ssid = "";
    private static long ssidAt;
    private static boolean ssidTried;

    /**
     * The Wi-Fi network's name, or "" when the TV is on a cable or has none. Cached for a minute: this asks the
     * system service, and the card is redrawn on every frame of the drawer's animation.
     */
    static String ssid(Context c) {
        long now = SystemClock.uptimeMillis();
        if (ssidTried && now - ssidAt < 60_000) return ssid;
        ssidTried = true;
        ssidAt = now;
        ssid = readSsid(c);
        return ssid;
    }

    private static String readSsid(Context c) {
        try {
            ConnectivityManager cm = c.getSystemService(ConnectivityManager.class);
            if (cm != null) {
                Network net = cm.getActiveNetwork();
                if (net != null) {
                    NetworkCapabilities caps = cm.getNetworkCapabilities(net);
                    if (caps != null && !caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                        // On Ethernet: name the link instead of leaving the row blank.
                        if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return "Ethernet";
                        return "";
                    }
                }
            }
        } catch (Exception ignored) {
        }
        try {
            WifiManager wm = (WifiManager) c.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm == null) return "";
            WifiInfo info = wm.getConnectionInfo();
            if (info == null) return "";
            String name = info.getSSID();
            if (name == null) return "";
            // The API quotes the name; some firmware wraps it twice, and an unknown network comes back as <unknown ssid>.
            name = name.trim();
            while (name.length() > 1 && name.startsWith("\"") && name.endsWith("\"")) {
                name = name.substring(1, name.length() - 1).trim();
            }
            if (name.isEmpty() || name.contains("<unknown")) return "";
            return name;
        } catch (Exception e) {
            // Android 10+ needs a location permission for the SSID and hands back an empty one without it: the row
            // then shows the signal strength alone, which needs no permission.
            return "";
        }
    }

    /** Signal strength 0 to 4 (the bars the icon draws), or -1 when unknown. */
    static int signal(Context c) {
        try {
            WifiManager wm = (WifiManager) c.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm == null) return -1;
            WifiInfo info = wm.getConnectionInfo();
            if (info == null) return -1;
            int rssi = info.getRssi();
            if (rssi <= -127 || rssi >= 0) return -1;
            if (rssi >= -55) return 4;
            if (rssi >= -67) return 3;
            if (rssi >= -78) return 2;
            return 1;
        } catch (Exception e) {
            return -1;
        }
    }

    /** The TV's own IPv4 address on the current link, or "" when there is none (the Network screen shows it). */
    static String ip(Context c) {
        try {
            ConnectivityManager cm = c.getSystemService(ConnectivityManager.class);
            if (cm == null) return "";
            Network net = cm.getActiveNetwork();
            if (net == null) return "";
            LinkProperties lp = cm.getLinkProperties(net);
            if (lp == null) return "";
            for (android.net.LinkAddress a : lp.getLinkAddresses()) {
                if (a.getAddress() instanceof java.net.Inet4Address) {
                    return a.getAddress().getHostAddress();
                }
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    /** "Wi-Fi", "Ethernet" or "No network": what the Network screen's first row says. */
    static String link(Context c) {
        try {
            ConnectivityManager cm = c.getSystemService(ConnectivityManager.class);
            if (cm == null) return "";
            Network net = cm.getActiveNetwork();
            if (net == null) return Ui.tr("No network");
            NetworkCapabilities caps = cm.getNetworkCapabilities(net);
            if (caps == null) return Ui.tr("No network");
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return "Wi-Fi";
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return "Ethernet";
            return Ui.tr("No network");
        } catch (Exception e) {
            return "";
        }
    }

    /** The capsule's one-line summary: the network's name, or the link when it has none. */
    static String networkLine(Context c) {
        String name = ssid(c);
        if (!name.isEmpty()) return name;
        String link = link(c);
        return link.isEmpty() ? "—" : link;
    }

    static String percent(int v) {
        return v < 0 ? "—" : String.format(Locale.ROOT, "%d%%", v);
    }

    static String megabytes(int v) {
        return v < 0 ? "—" : String.format(Locale.ROOT, "%d MB", v);
    }

    static String fpsText(int v) {
        return String.format(Locale.ROOT, "%d FPS", v);
    }

    /** A figure with one decimal, in the viewer's language ("2.4", "18,6"). */
    static String one(float v) {
        return String.format(Ui.locale(), "%.1f", v);
    }

    /** A size in MB, as GB when it has at least one ("18.6 GB", "820 MB"). */
    static String size(long mb) {
        if (mb < 0) return "—";
        return mb >= 1024 ? Ui.trf("{n} GB", "n", one(mb / 1024f)) : Ui.trf("{n} MB", "n", mb);
    }
}
