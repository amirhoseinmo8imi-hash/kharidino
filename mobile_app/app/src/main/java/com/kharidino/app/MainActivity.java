package com.kharidino.app;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.widget.ProgressBar;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.graphics.Color;
import android.view.Gravity;

public class MainActivity extends Activity {
    // Set this to the HTTPS deployment URL before building the distributable APK.
    private static final String APP_URL = "https://kharidino.ir/";
    private WebView web;
    private ProgressBar progress;
    private FrameLayout container;
    private TextView error;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        container = new FrameLayout(this);
        container.setBackgroundColor(Color.rgb(5,8,22));
        web = new WebView(this);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadsImagesAutomatically(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        error = new TextView(this);
        error.setText("اتصال به خریدینو برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.\n\nبرای تلاش مجدد لمس کنید.");
        error.setTextColor(Color.WHITE); error.setGravity(Gravity.CENTER); error.setTextSize(17);
        error.setVisibility(View.GONE); error.setOnClickListener(v -> web.reload());
        web.setWebViewClient(new WebViewClient(){
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap favicon){ progress.setVisibility(View.VISIBLE);error.setVisibility(View.GONE); }
            @Override public void onPageFinished(WebView view,String url){ progress.setVisibility(View.GONE); }
            @Override public void onReceivedError(WebView view,android.webkit.WebResourceRequest req,android.webkit.WebResourceError e){ if(req.isForMainFrame()){progress.setVisibility(View.GONE);error.setVisibility(View.VISIBLE;} }
        });
        container.addView(web,new FrameLayout.LayoutParams(-1,-1));
        container.addView(progress,new FrameLayout.LayoutParams(-1,8,Gravity.TOP));
        container.addView(error,new FrameLayout.LayoutParams(-1,-1));
        setContentView(container);
        if(savedInstanceState!=null) web.restoreState(savedInstanceState); else web.loadUrl(APP_URL);
    }
    @Override protected void onSaveInstanceState(Bundle out){super.onSaveInstanceState(out);web.saveState(out);}
    @Override public void onBackPressed(){if(web!=null && web.canGoBack())web.goBack();else super.onBackPressed();}
}
