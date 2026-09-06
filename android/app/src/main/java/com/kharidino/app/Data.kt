package com.kharidino.app

import androidx.room.*
import com.google.gson.JsonObject
import retrofit2.http.*

@Entity(tableName = "products")
data class ProductEntity(@PrimaryKey val id: Long, val name: String, val description: String = "", val price: Long = 0, val categoryId: Long? = null, val image: String = "", val active: Boolean = true)

@Entity(tableName = "sync_queue")
data class SyncOperation(@PrimaryKey val opId: String, val entity: String, val action: String, val clientId: Long?, val payload: String, val createdAt: Long = System.currentTimeMillis(), val attempts: Int = 0)

@Dao
interface KharidinoDao {
    @Query("SELECT * FROM products ORDER BY id DESC") suspend fun products(): List<ProductEntity>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertProducts(items: List<ProductEntity>)
    @Insert suspend fun queue(op: SyncOperation)
    @Query("SELECT * FROM sync_queue ORDER BY createdAt LIMIT 100") suspend fun pending(): List<SyncOperation>
    @Query("DELETE FROM sync_queue WHERE opId IN (:ids)") suspend fun remove(ids: List<String>)
    @Query("SELECT COUNT(*) FROM sync_queue") suspend fun pendingCount(): Int
}

@Database(entities = [ProductEntity::class, SyncOperation::class], version = 1, exportSchema = false)
abstract class KharidinoDb : RoomDatabase() { abstract fun dao(): KharidinoDao }

data class LoginRequest(val email: String, val password: String)
data class LoginResponse(val ok: Boolean, val token: String?, val error: String?)
data class ProductDto(val id: Long, val name: String, val description: String, val price: Long, val category_id: Long?, val image: String, val active: Boolean = true)
data class ProductPage(val items: List<ProductDto>, val total: Int)
data class SyncRequest(val operations: List<SyncDto>)
data class SyncDto(val op_id: String, val entity: String, val action: String, val client_id: Long?, val data: JsonObject)
data class SyncResponse(val ok: Boolean, val processed: Int?, val results: List<SyncResult>?, val error: String?)
data class SyncResult(val client_id: Long?, val server_id: Long?, val entity: String?, val action: String?)

interface KharidinoApi {
    @POST("api/mobile/auth/login") suspend fun login(@Body body: LoginRequest): LoginResponse
    @GET("api/mobile/products") suspend fun products(@Query("limit") limit: Int = 100): ProductPage
    @POST("api/mobile/sync/push") suspend fun push(@Header("Authorization") auth: String, @Body body: SyncRequest): SyncResponse
    @GET("api/mobile/sync/pull") suspend fun pull(@Header("Authorization") auth: String): PullResponse
}
data class PullResponse(val ok: Boolean, val products: List<ProductDto> = emptyList(), val error: String? = null)
