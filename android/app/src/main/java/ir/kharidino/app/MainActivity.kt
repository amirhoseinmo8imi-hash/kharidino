package ir.kharidino.app
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
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { KharidinoApp() }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun KharidinoApp() {
    var section by remember { mutableStateOf("market") }
    var rows by remember { mutableStateOf(listOf<String>()) }
    var status by remember { mutableStateOf("در حال اتصال به API خریدینو…") }
    val api = remember { PlatformApi.create() }
    fun load(target: String) {
        section = target
        status = "در حال دریافت اطلاعات…"
        when (target) {
            "market" -> api.products().enqueue(object : Callback<Paged<ProductItem>> {
                override fun onResponse(call: Call<Paged<ProductItem>>, response: Response<Paged<ProductItem>>) {
                    rows = response.body()?.items?.map { it.name + " — " + it.price + " تومان" } ?: emptyList()
                    status = if (response.isSuccessful) "بازار خریدینو" else "خطا در دریافت بازار: " + response.code()
                }
                override fun onFailure(call: Call<Paged<ProductItem>>, t: Throwable) { status = "اتصال برقرار نشد: " + t.localizedMessage; rows = emptyList() }
            })
            "explore" -> api.explore().enqueue(object : Callback<Paged<ExploreItem>> {
                override fun onResponse(call: Call<Paged<ExploreItem>>, response: Response<Paged<ExploreItem>>) {
                    rows = response.body()?.items?.map { it.author + ": " + it.caption } ?: emptyList()
                    status = if (response.isSuccessful) "اکسپلور خریدینو" else "خطا در دریافت اکسپلور: " + response.code()
                }
                override fun onFailure(call: Call<Paged<ExploreItem>>, t: Throwable) { status = "اتصال برقرار نشد: " + t.localizedMessage; rows = emptyList() }
            })
            "cinema" -> api.cinema().enqueue(object : Callback<Paged<CinemaItem>> {
                override fun onResponse(call: Call<Paged<CinemaItem>>, response: Response<Paged<CinemaItem>>) {
                    rows = response.body()?.items?.map { it.title + " · " + it.genre } ?: emptyList()
                    status = if (response.isSuccessful) "سینمای خریدینو" else "خطا در دریافت سینما: " + response.code()
                }
                override fun onFailure(call: Call<Paged<CinemaItem>>, t: Throwable) { status = "اتصال برقرار نشد: " + t.localizedMessage; rows = emptyList() }
            })
        }
    }
    LaunchedEffect(Unit) { load("market") }
    MaterialTheme {
        Scaffold(topBar = { TopAppBar(title = { Text("خریدینو") }) }, bottomBar = {
            NavigationBar {
                listOf("market" to "بازار", "explore" to "اکسپلور", "cinema" to "سینما").forEach { pair ->
                    NavigationBarItem(selected = section == pair.first, onClick = { load(pair.first) }, icon = {}, label = { Text(pair.second) })
                }
            }
        }) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
                Text(status, style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(12.dp))
                if (rows.isEmpty()) Text("محتوایی برای نمایش نیست یا API هنوز در دسترس نیست.")
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(rows) { row -> ElevatedCard(Modifier.fillMaxWidth()) { Text(row, Modifier.padding(16.dp)) } }
                }
                Spacer(Modifier.height(12.dp))
                Text("نشانی API هنگام build از KHARIDINO_API_BASE_URL تنظیم می‌شود.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
