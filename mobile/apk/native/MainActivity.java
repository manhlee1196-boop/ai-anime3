package vn.anime3.mobile;

import android.content.Intent;
import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Capacitor 4+ khởi tạo bridge trong super.onCreate; plugin phải đăng ký TRƯỚC.
        registerPlugin(Anime3MediaPlugin.class);
        registerPlugin(Anime3ColabPlugin.class);
        super.onCreate(savedInstanceState);
        Anime3ColabPlugin.captureConnectionIntent(getApplicationContext(), getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        Anime3ColabPlugin.captureConnectionIntent(getApplicationContext(), intent);
    }
}
