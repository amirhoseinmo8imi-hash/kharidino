package com.kharidino.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        scheduleKharidinoSync(this)
        val repo = KharidinoRepository(this)
        setContent { KharidinoApp(repo) }
    }
}

@Composable
fun KharidinoApp(repo: KharidinoRepository) {
    var server by remember { mutableStateOf(repo.server()) }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    var products by remember { mutableStateOf(emptyList<ProductEntity>()) }
    var pending by remember { mutableIntStateOf(0) }
    var status by remember { mutableStateOf("آماده به کار") }
    var loggedIn by remember { mutableStateOf(repo.token() != null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { products = repo.loadLocal(); pending = repo.pendingCount() }
    MaterialTheme {
        Surface(Modifier.fillMaxSize()) {
            Column(Modifier.fillMaxSize().padding(20.dp)) {
                Text("خریدینو", style = MaterialTheme.typography.headlineLarge)
                Text("اپ مدیریت آفلاین + همگام‌سازی", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(14.dp))
                OutlinedTextField(server, { server = it }, label = { Text("آدرس سرور") }, modifier = Modifier.fillMaxWidth())
                if (!loggedIn) {
                    OutlinedTextField(email, { email = it }, label = { Text("ایمیل مدیر") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(password, { password = it }, label = { Text("رمز مدیر") }, modifier = Modifier.fillMaxWidth())
                    Button(onClick = { scope.launch { repo.setServer(server); status = if (repo.login(email, password)) { loggedIn = true; "ورود موفق بود" } else "ورود ناموفق بود" } }, modifier = Modifier.fillMaxWidth()) { Text("ورود") }
                } else {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("در انتظار ارسال: $pending")
                        Button(onClick = { scope.launch { status = "در حال همگام‌سازی..."; try { val sent = repo.sync(); products = repo.loadLocal(); pending = repo.pendingCount(); status = "$sent تغییر ارسال شد" } catch (e: Exception) { status = "آفلاین/خطا: ${e.message}" } } }) { Text("همگام‌سازی") }
                    }
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(name, { name = it }, label = { Text("نام محصول") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(price, { price = it }, label = { Text("قیمت") }, modifier = Modifier.fillMaxWidth())
                    Button(onClick = { val p = price.toLongOrNull(); if (name.isNotBlank() && p != null) scope.launch { repo.addProductOffline(name, p); products = repo.loadLocal(); pending = repo.pendingCount(); status = "محصول محلی ذخیره شد؛ بعداً Sync می‌شود"; name = ""; price = "" } }, modifier = Modifier.fillMaxWidth()) { Text("افزودن محصول آفلاین") }
                    Spacer(Modifier.height(8.dp))
                    Text(status)
                    Spacer(Modifier.height(8.dp))
                    LazyColumn(Modifier.fillMaxSize()) { items(products) { Text("${it.name} — ${it.price}", Modifier.padding(8.dp)) } }
                }
            }
        }
    }
}
