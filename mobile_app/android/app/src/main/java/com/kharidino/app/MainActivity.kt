package com.kharidino.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { KharidinoApp() }
    }
}

private val Background = Color(0xFF070B14)
private val Surface = Color(0xFF101827)
private val Primary = Color(0xFF38BDF8)

@Composable
fun KharidinoApp() {
    var selected by remember { mutableIntStateOf(0) }
    Scaffold(
        containerColor = Background,
        bottomBar = {
            NavigationBar(containerColor = Surface) {
                val items = listOf("خانه", "جستجو", "سبد", "علاقه‌مندی", "حساب")
                val icons = listOf(Icons.Default.Home, Icons.Default.Search, Icons.Default.ShoppingCart, Icons.Default.FavoriteBorder, Icons.Default.Person)
                items.forEachIndexed { index, label ->
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
        HomeScreen(Modifier.padding(padding))
    }
}

@Composable
private fun HomeScreen(modifier: Modifier = Modifier) {
    val categories = listOf("موبایل", "لپ‌تاپ", "هدفون", "کنسول", "لوازم خانه")
    val products = listOf("Galaxy S24", "iPhone 16 Pro", "AirPods Pro 2", "PS5 Slim")

    Column(
        modifier = modifier.fillMaxSize().background(Background).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.weight(1f)) {
                Text("خریدینو", color = Color.White, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text("مقایسه کن، بهتر بخر", color = Color(0xFF94A3B8))
            }
            IconButton(onClick = {}) { Icon(Icons.Default.ShoppingCart, "سبد خرید", tint = Primary) }
        }

        OutlinedTextField(
            value = "",
            onValueChange = {},
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            placeholder = { Text("چی می‌خوای بخری؟") },
            leadingIcon = { Icon(Icons.Default.Search, "جستجو") }
        )

        Text("دسته‌بندی‌ها", color = Color.White, fontWeight = FontWeight.Bold)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            items(categories) { category ->
                Card(shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = Surface)) {
                    Text(category, color = Color.White, modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp))
                }
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Text("پیشنهادهای خریدینو", color = Color.White, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            TextButton(onClick = {}) { Text("مشاهده همه") }
        }

        LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            items(products) { product -> ProductCard(product) }
        }

        Spacer(Modifier.height(4.dp))
        Card(shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFF111D33)), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp)) {
                Text("🤖 Kharidino AI", color = Primary, fontWeight = FontWeight.Bold)
                Text("برای انتخاب محصول بهتر، از هوش مصنوعی خریدینو کمک بگیر.", color = Color.White, modifier = Modifier.padding(top = 6.dp))
            }
        }
    }
}

@Composable
private fun ProductCard(name: String) {
    Card(modifier = Modifier.size(width = 190.dp, height = 220.dp), shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = Surface)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Column(Modifier.fillMaxWidth().height(115.dp).background(Color(0xFF172235), RoundedCornerShape(16.dp)), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Icon(Icons.Default.ShoppingCart, null, tint = Primary, modifier = Modifier.size(48.dp))
            }
            Text(name, color = Color.White, fontWeight = FontWeight.Bold)
            Text("مقایسه قیمت", color = Color(0xFF94A3B8))
        }
    }
}
