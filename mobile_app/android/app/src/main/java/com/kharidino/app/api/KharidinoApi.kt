package com.kharidino.app.api

import com.kharidino.app.BuildConfig
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Path

val KHARIDINO_BASE_URL: String = BuildConfig.KHARIDINO_BASE_URL

data class Product(
    val id: Int,
    val name: String,
    val description: String = "",
    val price: Long = 0,
    val image: String = "",
    val category_id: Int? = null,
    val category: String = "",
    val offers: List<Offer> = emptyList()
)

data class Offer(
    val id: Int,
    val store_id: Int,
    val store: String,
    val price: Long,
    val url: String = "",
    val in_stock: Boolean = true
)

data class ProductResponse(
    val items: List<Product>,
    val total: Int,
    val offset: Int,
    val limit: Int
)

data class Category(
    val id: Int,
    val name: String,
    val icon: String = "",
    val description: String = ""
)

data class CategoryResponse(val items: List<Category>)

data class SearchResponse(val items: List<Product>, val total: Int)

interface KharidinoApi {
    @GET("api/mobile/health")
    suspend fun health(): Map<String, Any>

    @GET("api/mobile/categories")
    suspend fun categories(): CategoryResponse

    @GET("api/mobile/products")
    suspend fun products(
        @Query("category_id") categoryId: Int? = null,
        @Query("q") query: String? = null,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): ProductResponse

    @GET("api/mobile/products/{id}")
    suspend fun product(@Path("id") id: Int): Product

    @GET("api/mobile/search")
    suspend fun search(@Query("q") query: String): SearchResponse
}
