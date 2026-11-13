package vn.anime3.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Nhận callback sau khi notebook Colab đã tạo tunnel:
 *
 *   anime3://connect?url=https%3A%2F%2Fxxxx.gradio.live
 *
 * URL được giữ tạm trong SharedPreferences để không mất khi Android tạo lại Activity
 * hoặc WebView chưa nạp xong. Chỉ chấp nhận tunnel HTTPS do notebook chính thức hỗ trợ;
 * custom scheme có thể bị app khác gọi nên không được coi dữ liệu Intent là tin cậy.
 */
@CapacitorPlugin(name = "Anime3Colab")
public class Anime3ColabPlugin extends Plugin {
    private static final String PREFS = "anime3_colab_callback";
    private static final String KEY_URL = "pending_tunnel_url";

    public static void captureConnectionIntent(Context context, Intent intent) {
        if (context == null || intent == null || !Intent.ACTION_VIEW.equals(intent.getAction())) return;
        Uri uri = intent.getData();
        if (uri == null || !"anime3".equalsIgnoreCase(uri.getScheme())
                || !"connect".equalsIgnoreCase(uri.getHost())) return;
        String url = uri.getQueryParameter("url");
        if (!isSupportedTunnel(url)) return;
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_URL, url.trim()).apply();
    }

    @PluginMethod
    public void consumeConnection(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String url = prefs.getString(KEY_URL, "");
        // Callback là dùng một lần: không tự kết nối lại tunnel cũ mỗi lần mở app.
        prefs.edit().remove(KEY_URL).apply();
        JSObject result = new JSObject();
        result.put("url", url == null ? "" : url);
        call.resolve(result);
    }

    private static boolean isSupportedTunnel(String raw) {
        if (raw == null || raw.trim().isEmpty()) return false;
        try {
            Uri target = Uri.parse(raw.trim());
            String host = target.getHost();
            if (host == null || !"https".equalsIgnoreCase(target.getScheme())) return false;
            String lower = host.toLowerCase();
            return lower.endsWith(".gradio.live") || lower.endsWith(".trycloudflare.com");
        } catch (Exception ignored) {
            return false;
        }
    }
}
