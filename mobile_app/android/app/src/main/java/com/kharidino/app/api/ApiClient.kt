package com.kharidino.app.api

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object ApiClient {
    val service: KharidinoApi by lazy {
        Retrofit.Builder()
            .baseUrl(KHARIDINO_BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(KharidinoApi::class.java)
    }
}
