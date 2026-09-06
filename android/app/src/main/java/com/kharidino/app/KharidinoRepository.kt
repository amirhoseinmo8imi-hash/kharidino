package com.kharidino.app

import android.content.Context
import androidx.room.Room
import com.google.gson.Gson
import com.google.gson.JsonObject
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.UUID

class KharidinoRepository(context: Context) {
    private val prefs = context.getSharedPreferences("kharidino", Context.MODE_PRIVATE)
    private val gson = Gson()
    private val db = Room.databaseBuilder(context, KharidinoDb::class.java, "kharidino-offline.db").build()
    private val api: KharidinoApi

    init {
        val client = OkHttpClient.Builder().build()
        api = Retrofit.Builder().baseUrl(normalize(prefs.getString("server", "http://10.0.2.2:5000")!!))
            .client(client).addConverterFactory(GsonConverterFactory.create()).build().create(KharidinoApi::class.java)
    }

    fun setServer(url: String) = prefs.edit().putString("server", normalize(url)).apply()
    fun server() = prefs.getString("server", "http://10.0.2.2:5000")!!
    fun token() = prefs.getString("token", null)
    fun saveToken(token: String) = prefs.edit().putString("token", token).apply()

    suspend fun login(email: String, password: String): Boolean {
        val response = api.login(LoginRequest(email, password))
        if (response.ok && !response.token.isNullOrBlank()) { saveToken(response.token); return true }
        return false
    }

    suspend fun loadLocal() = db.dao().products()
    suspend fun pendingCount() = db.dao().pendingCount()

    suspend fun refresh(): Int {
        val t = token() ?: error("ابتدا وارد حساب مدیر شوید")
        val response = api.pull("Bearer $t")
        if (!response.ok) error(response.error ?: "خطای دریافت اطلاعات")
        db.dao().upsertProducts(response.products.map { ProductEntity(it.id, it.name, it.description, it.price, it.category_id, it.image, it.active) })
        return response.products.size
    }

    suspend fun addProductOffline(name: String, price: Long): Long {
        val id = -System.currentTimeMillis()
        val product = ProductEntity(id, name, price = price)
        db.dao().upsertProducts(listOf(product))
        val payload = gson.toJson(mapOf("name" to name, "description" to "", "price" to price, "category_id" to null, "image" to "", "active" to true))
        db.dao().queue(SyncOperation(UUID.randomUUID().toString(), "product", "create", id, payload))
        return id
    }

    suspend fun sync(): Int {
        val t = token() ?: error("ابتدا وارد حساب مدیر شوید")
        val pending = db.dao().pending()
        if (pending.isNotEmpty()) {
            val ops = pending.map { op -> SyncDto(op.opId, op.entity, op.action, op.clientId, gson.fromJson(op.payload, JsonObject::class.java)) }
            val pushed = api.push("Bearer $t", SyncRequest(ops))
            if (!pushed.ok) error(pushed.error ?: "همگام‌سازی ناموفق بود")
            db.dao().remove(pending.map { it.opId })
        }
        refresh()
        return pending.size
    }

    private fun normalize(value: String): String = if (value.endsWith("/")) value else "$value/"
}
