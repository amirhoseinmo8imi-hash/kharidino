package com.kharidino.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.filled.Storefront
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kharidino.app.api.ApiClient
import com.kharidino.app.api.Category
import com.kharidino.app.api.Product

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { KharidinoApp() }
    }
}

private val Background = Color(0xFF070B14)
private val SurfaceColor = Color(0xFF101827)
private val Surface2 = Color(0xFF172235)
private val Primary = Color(0xFF38BDF8)
private val Muted = Color(0xFF94A3B8)
private val Success = Color(0xFF34D399)

@Composable
fun KharidinoApp() {
    var selected by remember { mutableIntStateOf(0) }
    val labels = listOf("خانه", "جستجو", "سبد", "فروشگاه‌ها", "حساب")
    val icons = listOf(Icons.Default.Home, Icons.Default.Search, Icons.Default.ShoppingCart, Icons.Default.Storefront, Icons.Default.Person)

    Scaffold(
        containerColor = Background,
        bottomBar = {
            NavigationBar(containerColor = SurfaceColor) {
                labels.forEachIndexed { index, label ->
                    NavigationBarItem(
                        selected = selected == index,
                        onClick = { selected = index },
                        icon = { Icon(icons[index], label) },
                        label = { Text(label) }
                    )
                }
            }
        }
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            when (selected) {
                0 -> HomeScreen()
                1 -> SearchScreen()
                2 -> PlaceholderScreen("سبد خرید", "محصولات انتخابی شما اینجا نمایش داده می‌شوند.", Icons.Default.ShoppingCart)
                3 -> StoresScreen()
                else -> PlaceholderScreen("حساب کاربری", "ورود، سفارش‌ها، آدرس‌ها و تنظیمات حساب.", Icons.Default.Person)
            }
        }
    }
}

@Composable
private fun HomeScreen() {
    var products by remember { mutableStateOf<List<Product>>(emptyList()) }
    var categories by remember { mutableStateOf<List<Category>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var search by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(Unit) {
        try {
            products = ApiClient.service.products(limit = 60).items
            categories = ApiClient.service.categories().items
            error = null
        } catch (_: Exception) {
            error = "اتصال به سرور خریدینو برقرار نشد."
        } finally { loading = false }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Background).padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { HomeHeader(search) { search = it } }
        item { HeroBanner() }
        item {
            SectionTitle("دسته‌بندی‌ها", "همه")
            LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                item { CategoryChip("همه", selectedCategory == null) { selectedCategory = null } }
                items(categories.take(12)) { category ->
                    CategoryChip(category.name, selectedCategory == category.id) { selectedCategory = category.id }
                }
            }
        }
        if (loading) item {
            CircularProgressIndicator(color = Primary, modifier = Modifier.padding(32.dp).size(34.dp).align(Alignment.CenterHorizontally))
        }
        if (error != null) item { Text(error!!, color = Color(0xFFFF8A8A)) }
        if (!loading && error == null) {
            val filtered = products.filter {
                (selectedCategory == null || it.category_id == selectedCategory) &&
                    (search.isBlank() || it.name.contains(search, ignoreCase = true))
            }
            item {
                SectionTitle("پیشنهادهای امروز", "مشاهده همه")
                ProductRail(filtered.take(12))
            }
            categories.take(6).forEach { category ->
                val categoryProducts = products.filter { it.category_id == category.id }.take(10)
                if (categoryProducts.isNotEmpty()) {
                    item {
                        SectionTitle(category.name, "بیشتر")
                        ProductRail(categoryProducts)
                    }
                }
            }
        }
        item { StoresPreview() }
        item { AiCard() }
        item { Spacer(Modifier.height(20.dp)) }
    }
}

@Composable
private fun HomeHeader(search: String, onSearch: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(top = 18.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("خریدینو", color = Color.White, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.ExtraBold)
                Text("مقایسه کن، بهتر بخر", color = Muted)
            }
            IconButton(onClick = {}) { Icon(Icons.Default.ShoppingCart, "سبد خرید", tint = Primary) }
            IconButton(onClick = {}) { Icon(Icons.Default.Person, "حساب", tint = Color.White) }
        }
        OutlinedTextField(
            value = search,
            onValueChange = onSearch,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            placeholder = { Text("چی می‌خوای بخری؟", color = Muted) },
            leadingIcon = { Icon(Icons.Default.Search, "جستجو", tint = Primary) },
            shape = RoundedCornerShape(18.dp)
        )
    }
}

@Composable
private fun HeroBanner() {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(26.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFF11243A))) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("خرید هوشمند، یک قدم جلوتر", color = Color.White, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleLarge)
                Text("محصولات و فروشنده‌ها را کنار هم مقایسه کن.", color = Muted)
                Button(onClick = {}) { Text("شروع خرید") }
            }
            Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(58.dp))
        }
    }
}

@Composable
private fun CategoryChip(name: String, selected: Boolean, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.clip(RoundedCornerShape(16.dp)).clickable(onClick = onClick),
        color = if (selected) Primary else Surface2,
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(name, color = if (selected) Background else Color.White, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 15.dp, vertical = 11.dp))
    }
}

@Composable
private fun SectionTitle(title: String, action: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = Color.White, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
        Text(action, color = Primary, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun ProductRail(products: List<Product>) {
    if (products.isEmpty()) {
        Text("محصولی برای نمایش وجود ندارد.", color = Muted)
        return
    }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        itemsIndexed(products) { index, product -> AnimatedProductCard(product, index) }
    }
}

@Composable
private fun AnimatedProductCard(product: Product, index: Int) {
    var favorite by remember { mutableStateOf(false) }
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { visible = true }
    val scale by animateFloatAsState(if (visible) 1f else 0.94f, label = "product-scale-$index")
    Card(modifier = Modifier.width(190.dp).height(270.dp).scale(scale), shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = SurfaceColor)) {
        Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Box(Modifier.fillMaxWidth().height(132.dp).clip(RoundedCornerShape(17.dp)).background(Surface2)) {
                Icon(Icons.Default.ShoppingCart, null, tint = Primary, modifier = Modifier.size(48.dp).align(Alignment.Center))
                IconButton(onClick = { favorite = !favorite }, modifier = Modifier.align(Alignment.TopEnd)) {
                    Icon(if (favorite) Icons.Default.Favorite else Icons.Default.FavoriteBorder, "علاقه‌مندی", tint = if (favorite) Color(0xFFFF5A78) else Color.White)
                }
            }
            Text(product.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(if (product.category.isNotBlank()) product.category else "محصول خریدینو", color = Muted, style = MaterialTheme.typography.bodySmall)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${product.price} تومان", color = Primary, fontWeight = FontWeight.ExtraBold, modifier = Modifier.weight(1f))
                if (product.offers.isNotEmpty()) Text("${product.offers.size} فروشنده", color = Success, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun StoresPreview() {
    Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = SurfaceColor), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle("فروشگاه‌های منتخب خریدینو", "مشاهده همه")
            LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                items((1..8).toList()) { number ->
                    Column(Modifier.width(130.dp).clip(RoundedCornerShape(18.dp)).background(Surface2).padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(58.dp).clip(CircleShape).background(Background), contentAlignment = Alignment.Center) { Icon(Icons.Default.Storefront, null, tint = Primary) }
                        Spacer(Modifier.height(8.dp))
                        Text("فروشگاه $number", color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1)
                        Text("فعال و آماده خرید", color = Success, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun AiCard() {
    Card(shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFF111D33)), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.AutoAwesome, null, tint = Primary, modifier = Modifier.size(42.dp))
            Column(Modifier.padding(start = 12.dp)) {
                Text("Kharidino AI", color = Primary, fontWeight = FontWeight.ExtraBold)
                Text("برای انتخاب محصول بهتر، از هوش مصنوعی خریدینو کمک بگیر.", color = Color.White, modifier = Modifier.padding(top = 5.dp))
            }
        }
    }
}

@Composable
private fun SearchScreen() {
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<Product>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var searched by remember { mutableStateOf(false) }

    LaunchedEffect(query) {
        if (query.trim().length >= 2) {
            loading = true
            try { results = ApiClient.service.search(query.trim()).items } catch (_: Exception) { results = emptyList() }
            loading = false
            searched = true
        } else if (query.isBlank()) { results = emptyList(); searched = false }
    }

    LazyColumn(Modifier.fillMaxSize().background(Background).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Text("جستجوی خریدینو", color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold) }
        item { OutlinedTextField(query, { query = it }, modifier = Modifier.fillMaxWidth(), singleLine = true, placeholder = { Text("نام محصول را وارد کن") }, leadingIcon = { Icon(Icons.Default.Search, null, tint = Primary) }) }
        if (loading) item { CircularProgressIndicator(color = Primary) }
        if (searched && !loading) {
            item { Text("${results.size} نتیجه", color = Muted) }
            items(results) { SearchResultCard(it) }
        }
    }
}

@Composable
private fun SearchResultCard(product: Product) {
    Card(shape = RoundedCornerShape(20.dp), colors = CardDefaults.cardColors(containerColor = SurfaceColor), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(84.dp).clip(RoundedCornerShape(15.dp)).background(Surface2), contentAlignment = Alignment.Center) { Icon(Icons.Default.ShoppingCart, null, tint = Primary) }
            Column(Modifier.padding(start = 12.dp).weight(1f)) {
                Text(product.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(6.dp))
                Text("${product.price} تومان", color = Primary, fontWeight = FontWeight.ExtraBold)
                if (product.offers.isNotEmpty()) Text("مقایسه ${product.offers.size} فروشنده", color = Success, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun StoresScreen() {
    LazyColumn(Modifier.fillMaxSize().background(Background).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("فروشگاه‌های منتخب خریدینو", color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold) }
        items((1..8).toList()) { number ->
            Card(shape = RoundedCornerShape(20.dp), colors = CardDefaults.cardColors(containerColor = SurfaceColor), modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(64.dp).clip(CircleShape).background(Surface2), contentAlignment = Alignment.Center) { Icon(Icons.Default.Storefront, null, tint = Primary) }
                    Column(Modifier.padding(start = 12.dp).weight(1f)) {
                        Text("فروشگاه $number", color = Color.White, fontWeight = FontWeight.Bold)
                        Text("فروشنده فعال خریدینو", color = Muted)
                    }
                    Text("فعال", color = Success, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun PlaceholderScreen(title: String, subtitle: String, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Column(Modifier.fillMaxSize().background(Background).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Box(Modifier.size(88.dp).clip(CircleShape).background(Surface2), contentAlignment = Alignment.Center) { Icon(icon, null, tint = Primary, modifier = Modifier.size(42.dp)) }
        Spacer(Modifier.height(18.dp))
        Text(title, color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
        Spacer(Modifier.height(8.dp))
        Text(subtitle, color = Muted)
    }
}
