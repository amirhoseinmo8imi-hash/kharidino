package com.kharidino.app

import android.annotation.SuppressLint
import android.content.Intent
import android.app.DownloadManager
import android.net.Uri
import android.webkit.ValueCallback
import android.webkit.URLUtil
import android.os.Environment
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
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
    private var uploadCallback: ValueCallback<Array<Uri>>? = null
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
        root = FrameLayout(this).apply {
            setBackgroundColor(android.graphics.Color.rgb(7, 11, 20))
        }
        val density = resources.displayMetrics.density
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding((28 * density).toInt(), (24 * density).toInt(), (28 * density).toInt(), (24 * density).toInt())
        }
        val logo = ImageView(this).apply {
            setImageResource(R.drawable.ic_kharidino_mark)
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "لوگوی خریدینو"
        }
        content.addView(logo, LinearLayout.LayoutParams((112 * density).toInt(), (112 * density).toInt()).apply {
            bottomMargin = (22 * density).toInt()
        })
        status = TextView(this).apply {
            text = "در حال آماده‌سازی خریدینو…"
            setTextColor(android.graphics.Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
        }
        content.addView(status, LinearLayout.LayoutParams(-1, -2).apply {
            bottomMargin = (20 * density).toInt()
        })
        progress = ProgressBar(this)
        content.addView(progress, LinearLayout.LayoutParams(-2, -2))
        root.addView(content, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))
        setContentView(root)
    }

    private fun installWebsiteBundle() {
        val marker = File(filesDir, ".kharidino_bundle_version")
        val version = BuildConfig.VERSION_CODE.toString()
        if (marker.exists() && marker.readText() == version) return
        copyAssetTree("kharidino", File(filesDir, "kharidino"))
        marker.writeText(version)
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
                    if (uri.scheme == "mailto" || uri.scheme == "tel" || uri.scheme == "sms" || uri.scheme == "geo") {
                        return try {
                            startActivity(Intent(Intent.ACTION_VIEW, uri))
                            true
                        } catch (_: Exception) { true }
                    }
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
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    webView: WebView?,
                    filePathCallback: ValueCallback<Array<Uri>>?,
                    fileChooserParams: WebChromeClient.FileChooserParams?
                ): Boolean {
                    if (filePathCallback == null || fileChooserParams == null) return false
                    uploadCallback?.onReceiveValue(null)
                    uploadCallback = filePathCallback
                    return try {
                        startActivityForResult(fileChooserParams.createIntent(), FILE_PICKER_REQUEST)
                        true
                    } catch (_: Exception) {
                        uploadCallback?.onReceiveValue(null)
                        uploadCallback = null
                        false
                    }
                }
            }
            setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
                try {
                    val request = DownloadManager.Request(Uri.parse(url))
                    request.setMimeType(mimeType)
                    CookieManager.getInstance().getCookie(url)?.let { request.addRequestHeader("Cookie", it) }
                    if (!userAgent.isNullOrBlank()) request.addRequestHeader("User-Agent", userAgent)
                    request.setTitle(URLUtil.guessFileName(url, contentDisposition, mimeType))
                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    request.setDestinationInExternalFilesDir(this@MainActivity, Environment.DIRECTORY_DOWNLOADS, URLUtil.guessFileName(url, contentDisposition, mimeType))
                    (getSystemService(DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
                    Toast.makeText(this@MainActivity, "دانلود آغاز شد.", Toast.LENGTH_SHORT).show()
                } catch (_: Exception) {
                    Toast.makeText(this@MainActivity, "دانلود انجام نشد.", Toast.LENGTH_SHORT).show()
                }
            }
            CookieManager.getInstance().setAcceptCookie(true)
            CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
            loadUrl(localUrl)
        }
        root.removeAllViews()
        root.addView(webView, FrameLayout.LayoutParams(-1, -1))
    }

    @Deprecated("Deprecated in Android")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FILE_PICKER_REQUEST) {
            uploadCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
            uploadCallback = null
        }
    }

    override fun onDestroy() {
        uploadCallback?.onReceiveValue(null)
        uploadCallback = null
        if (::webView.isInitialized) webView.destroy()
        executor.shutdownNow()
        super.onDestroy()
    }

    companion object {
        private const val FILE_PICKER_REQUEST = 7301
    }
}
