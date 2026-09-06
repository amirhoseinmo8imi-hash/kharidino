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
    private var api: KharidinoApi = buildApi(server())

    private fun buildApi(url: String): KharidinoApi = Retrofit.Builder().baseUrl(normalize(url))
        .client(OkHttpClient.Builder().build()).addConverterFactory(GsonConverterFactory.create()).build().create(KharidinoApi::class.java)

    fun setServer(url: String) { val clean = normalize(url); prefs.edit().putString("server", clean).apply(); api = buildApi(clean) }
    fun server() = prefs.getString("server", "http://10.0.2.2:5000")!!
    fun token() = prefs.getString("token", null)
    private fun saveToken(token: String) = prefs.edit().putString("token", token).apply()
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
        db.dao().upsertProducts(listOf(ProductEntity(id, name, price = price)))
        val payload = gson.toJson(mapOf("name" to name, "description" to "", "price" to price, "image" to "", "active" to true))
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
            val negativeIds = pushed.results.orEmpty().mapNotNull { if ((it.client_id ?: 0) < 0) it.client_id else null }
            if (negativeIds.isNotEmpty()) db.dao().deleteProducts(negativeIds)
            db.dao().remove(pending.map { it.opId })
        }
        refresh()
        return pending.size
    }
    private fun normalize(value: String): String = if (value.endsWith("/")) value else "$value/"
}
