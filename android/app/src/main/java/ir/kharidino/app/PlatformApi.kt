package ir.kharidino.app
import retrofit2.Call
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET

data class PlatformModule(val id: String, val title: String, val path: String)
data class PlatformManifest(val name: String, val api_version: String, val modules: List<PlatformModule>)
data class ProductItem(val id: Int, val name: String, val description: String, val price: Int, val image: String)
data class ExploreItem(val id: Int, val caption: String, val media_type: String, val media_url: String, val author: String, val likes: Int)
data class CinemaItem(val id: Int, val title: String, val synopsis: String, val genre: String, val release_year: Int?, val poster_url: String, val has_video: Boolean)
data class Paged<T>(val items: List<T>, val page: Int, val per_page: Int, val total: Int)
interface PlatformApi {
    @GET("api/v1/platform") fun manifest(): Call<PlatformManifest>
    @GET("api/v1/market/products") fun products(): Call<Paged<ProductItem>>
    @GET("api/v1/explore/feed") fun explore(): Call<Paged<ExploreItem>>
    @GET("api/v1/cinema/titles") fun cinema(): Call<Paged<CinemaItem>>
    companion object {
        fun create(): PlatformApi = Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL)
            .addConverterFactory(GsonConverterFactory.create()).build().create(PlatformApi::class.java)
    }
}
