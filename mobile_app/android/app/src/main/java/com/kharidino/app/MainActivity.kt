package com.kharidino.app

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var root: FrameLayout
    private lateinit var status: TextView
    private lateinit var progress: ProgressBar
    private lateinit var webView: WebView
    private val localUrl = "http://127.0.0.1:8765/"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showStartup()
        executor.execute {
            try {
                installWebsiteBundle()
                if (!Python.isStarted()) Python.start(AndroidPlatform(this))
                Python.getInstance().getModule("android_server")
                    .callAttr("start", File(filesDir, "kharidino").absolutePath, 8765)
                runOnUiThread { showWebsite() }
            } catch (error: Exception) {
                runOnUiThread {
                    progress.visibility = View.GONE
                    status.text = "راه‌اندازی خریدینو انجام نشد. برنامه را دوباره باز کن.\n\n" + error.message
                }
            }
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (::webView.isInitialized && webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }

    private fun showStartup() {
        root = FrameLayout(this).apply { setBackgroundColor(android.graphics.Color.rgb(7, 11, 20)) }
        status = TextView(this).apply {
            text = "در حال آماده‌سازی فروشگاه داخلی خریدینو…"
            setTextColor(android.graphics.Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
        }
        progress = ProgressBar(this)
        root.addView(status, FrameLayout.LayoutParams(-1, -1))
        root.addView(progress, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
        setContentView(root)
    }

    private fun installWebsiteBundle() {
        copyAssetTree("kharidino", File(filesDir, "kharidino"))
        File(filesDir, ".kharidino_bundle_version").writeText("1")
    }

    private fun copyAssetTree(assetPath: String, target: File) {
        val children = assets.list(assetPath) ?: emptyArray()
        if (children.isNotEmpty()) {
            if (!target.exists()) target.mkdirs()
            children.forEach { child -> copyAssetTree("$assetPath/$child", File(target, child)) }
            return
        }
        val relative = assetPath.removePrefix("kharidino/")
        if (relative.startsWith("static/uploads/") && target.exists()) return
        target.parentFile?.mkdirs()
        assets.open(assetPath).use { input -> target.outputStream().use { input.copyTo(it) } }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun showWebsite() {
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.databaseEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.setSupportMultipleWindows(false)
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val uri = request.url
                    if (uri.scheme == "http" && uri.host == "127.0.0.1" && uri.port == 8765) return false
                    if (uri.scheme == "http" || uri.scheme == "https") {
                        return try {
                            startActivity(Intent(Intent.ACTION_VIEW, uri))
                            true
                        } catch (_: Exception) {
                            Toast.makeText(this@MainActivity, "برای باز کردن این پیوند اینترنت لازم است.", Toast.LENGTH_SHORT).show()
                            true
                        }
                    }
                    return true
                }
            }
            webChromeClient = WebChromeClient()
            CookieManager.getInstance().setAcceptCookie(true)
            CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
            loadUrl(localUrl)
        }
        root.removeAllViews()
        root.addView(webView, FrameLayout.LayoutParams(-1, -1))
    }

    override fun onDestroy() {
        if (::webView.isInitialized) webView.destroy()
        executor.shutdownNow()
        super.onDestroy()
    }
}
