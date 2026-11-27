package com.kharidino.app.api

/**
 * Lightweight catalog model used by the offline-first Android storefront.
 * Prices are stored in the app's display currency unit (toman).
 */
data class Product(
    val id: Int,
    val name: String,
    val description: String,
    val price: Long,
    val category: String = "عمومی"
)
