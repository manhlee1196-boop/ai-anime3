package vn.anime3.mobile;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;

/** Lưu ảnh vào thư viện media của Android, không dùng download blob của WebView. */
@CapacitorPlugin(name = "Anime3Media")
public class Anime3MediaPlugin extends Plugin {
    @PluginMethod
    public void saveImage(PluginCall call) {
        String encoded = call.getString("data", "");
        String mime = call.getString("mime", "image/png");
        String name = safeName(call.getString("name", "anime3.png"));
        if (encoded.isEmpty()) {
            call.reject("Không có dữ liệu ảnh để lưu");
            return;
        }
        try {
            byte[] bytes = Base64.decode(encoded, Base64.DEFAULT);
            if (bytes.length == 0) {
                call.reject("Dữ liệu ảnh rỗng");
                return;
            }
            String displayName = System.currentTimeMillis() + "-" + name;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                saveMediaStore(call, bytes, displayName, mime);
            } else {
                saveLegacy(call, bytes, displayName, mime);
            }
        } catch (IllegalArgumentException error) {
            call.reject("Dữ liệu ảnh base64 không hợp lệ", error);
        } catch (IOException error) {
            call.reject("Không ghi được ảnh: " + error.getMessage(), error);
        } catch (Exception error) {
            call.reject("Không lưu được ảnh: " + error.getMessage(), error);
        }
    }

    private String safeName(String value) {
        String cleaned = value == null ? "" : value.replaceAll("[^A-Za-z0-9._-]", "_");
        if (cleaned.isEmpty() || cleaned.equals(".") || cleaned.equals("..")) {
            return "anime3.png";
        }
        return cleaned.length() > 100 ? cleaned.substring(cleaned.length() - 100) : cleaned;
    }

    private void saveMediaStore(PluginCall call, byte[] bytes, String name, String mime)
            throws IOException {
        ContentResolver resolver = getContext().getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
        values.put(MediaStore.Images.Media.MIME_TYPE, mime);
        values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Anime3");
        values.put(MediaStore.Images.Media.IS_PENDING, 1);
        Uri uri = resolver.insert(
                MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values);
        if (uri == null) throw new IOException("MediaStore không tạo được mục ảnh");

        boolean complete = false;
        try {
            try (OutputStream output = resolver.openOutputStream(uri, "w")) {
                if (output == null) throw new IOException("Không mở được luồng ghi ảnh");
                output.write(bytes);
            }
            ContentValues published = new ContentValues();
            published.put(MediaStore.Images.Media.IS_PENDING, 0);
            resolver.update(uri, published, null, null);
            complete = true;
        } finally {
            if (!complete) resolver.delete(uri, null, null);
        }

        JSObject result = new JSObject();
        result.put("path", "Pictures/Anime3/" + name);
        result.put("uri", uri.toString());
        call.resolve(result);
    }

    private void saveLegacy(PluginCall call, byte[] bytes, String name, String mime)
            throws IOException {
        // Android 9 trở xuống: thư mục app-specific không cần quyền ghi external storage.
        File pictures = getContext().getExternalFilesDir(Environment.DIRECTORY_PICTURES);
        if (pictures == null) throw new IOException("Bộ nhớ ngoài chưa sẵn sàng");
        File directory = new File(pictures, "Anime3");
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("Không tạo được thư mục Anime3");
        }
        File output = new File(directory, name);
        try (FileOutputStream stream = new FileOutputStream(output)) {
            stream.write(bytes);
        }
        MediaScannerConnection.scanFile(
                getContext(), new String[]{output.getAbsolutePath()}, new String[]{mime}, null);

        JSObject result = new JSObject();
        result.put("path", "Android/data/vn.anime3.mobile/files/Pictures/Anime3/" + name);
        result.put("uri", Uri.fromFile(output).toString());
        call.resolve(result);
    }
}
