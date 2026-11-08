package vn.anime3.mobile;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Capacitor 4+ khởi tạo bridge trong super.onCreate; plugin phải đăng ký TRƯỚC.
        registerPlugin(Anime3MediaPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
