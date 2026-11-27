package com.kharidino.app
import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.kharidino.app.api.Product

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { KharidinoOfflineApp(applicationContext) } }
}
private val Background=Color(0xFFF5F7FB); private val SurfaceColor=Color.White; private val Primary=Color(0xFF0D9488)
private val categories=listOf("همه","موبایل","لوازم دیجیتال","کامپیوتر","خانه","گیمینگ")
private val demoProducts=listOf(
 Product(1,"گوشی سامسونگ Galaxy S24","نمونه محصول محلی خریدینو",45900000,category="موبایل"),
 Product(2,"هدفون بی‌سیم","هدفون بی‌سیم با کیفیت صدا",2350000,category="لوازم دیجیتال"),
 Product(3,"لپ‌تاپ سبک","مناسب کار و استفاده روزانه",38900000,category="کامپیوتر"),
 Product(4,"کنسول بازی","کنسول بازی نسل جدید",32500000,category="گیمینگ"),
 Product(5,"ساعت هوشمند","ساعت هوشمند با امکانات روز",4800000,category="لوازم دیجیتال"),
 Product(6,"اسپیکر بلوتوث","اسپیکر قابل حمل",1650000,category="لوازم دیجیتال"),
 Product(7,"چراغ مطالعه","چراغ مطالعه رومیزی",950000,category="خانه"),
 Product(8,"کیبورد مکانیکی","کیبورد مناسب بازی و تایپ",3200000,category="گیمینگ"))
private fun money(v:Long)="%,d".format(v)+" تومان"
@Composable fun KharidinoOfflineApp(context:Context){
 val prefs=remember{context.getSharedPreferences("kharidino_local",Context.MODE_PRIVATE)}
 var tab by remember{mutableIntStateOf(0)}; var search by remember{mutableStateOf("")}; var category by remember{mutableStateOf("همه")}
 var cart by remember{mutableStateOf(prefs.getStringSet("cart",emptySet())?.toSet()?:emptySet())}; var favorites by remember{mutableStateOf(prefs.getStringSet("favorites",emptySet())?.toSet()?:emptySet())}
 fun save(k:String,v:Set<String>){prefs.edit().putStringSet(k,v.toSet()).apply()}
 fun flip(s:Set<String>,id:String)=if(id in s)s-id else s+id
 val filtered=demoProducts.filter{(category=="همه"||it.category==category)&&(search.isBlank()||it.name.contains(search,true)||it.category.contains(search,true))}
 Scaffold(containerColor=Background,bottomBar={NavigationBar(containerColor=SurfaceColor){val labels=listOf("خانه","جستجو","سبد","علاقه‌مندی","حساب");val icons=listOf(Icons.Default.Home,Icons.Default.Search,Icons.Default.ShoppingCart,Icons.Default.FavoriteBorder,Icons.Default.Person);labels.forEachIndexed{i,l->NavigationBarItem(selected=tab==i,onClick={tab=i},icon={Icon(icons[i],contentDescription=l)},label={Text(l)})}}}){padding->
 Column(Modifier.fillMaxSize().padding(padding).padding(horizontal=16.dp,vertical=12.dp)){
 Row(verticalAlignment=Alignment.CenterVertically,modifier=Modifier.fillMaxWidth()){Column(Modifier.weight(1f)){Text("خریدینو",color=Primary,style=MaterialTheme.typography.headlineMedium,fontWeight=FontWeight.Bold);Text("مقایسه کن، بهتر بخر",color=Color(0xFF64748B))};Text("🛍️",style=MaterialTheme.typography.headlineMedium)}
 Spacer(Modifier.height(12.dp))
 when(tab){
 0,1->{OutlinedTextField(search,{search=it},modifier=Modifier.fillMaxWidth(),singleLine=true,placeholder={Text("چی می‌خوای بخری؟")},leadingIcon={Icon(Icons.Default.Search,contentDescription="جستجو")});Spacer(Modifier.height(8.dp))
 LazyRow(horizontalArrangement=Arrangement.spacedBy(4.dp)){items(categories){c->TextButton(onClick={category=c}){Text(if(category==c)"● $c" else c,color=if(category==c)Primary else Color.DarkGray)}}}
 Text(if(tab==1)"جستجوی محصولات (محلی)" else "محصولات منتخب",fontWeight=FontWeight.Bold,style=MaterialTheme.typography.titleLarge);Spacer(Modifier.height(8.dp))
 LazyColumn(verticalArrangement=Arrangement.spacedBy(10.dp)){items(filtered){p->ProductRow(p,p.id.toString() in cart,p.id.toString() in favorites,{cart=flip(cart,p.id.toString());save("cart",cart)},{favorites=flip(favorites,p.id.toString());save("favorites",favorites)})}}
 }
 2->{Text("سبد خرید محلی",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold);val inCart=demoProducts.filter{it.id.toString() in cart};if(inCart.isEmpty())Text("سبد خریدت خالی است. محصولات را اضافه کن.") else {LazyColumn(verticalArrangement=Arrangement.spacedBy(10.dp)){items(inCart){p->ProductRow(p,true,p.id.toString() in favorites,{cart=flip(cart,p.id.toString());save("cart",cart)},{favorites=flip(favorites,p.id.toString());save("favorites",favorites)})}};Spacer(Modifier.height(8.dp));Text("جمع تقریبی: "+money(inCart.sumOf{it.price}),fontWeight=FontWeight.Bold,color=Primary);Text("سبد روی گوشی ذخیره می‌شود؛ ثبت سفارش آنلاین در آینده.")}}
 3->{Text("علاقه‌مندی‌های محلی",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold);val fav=demoProducts.filter{it.id.toString() in favorites};if(fav.isEmpty())Text("هنوز محصولی ذخیره نکرده‌ای.");LazyColumn(verticalArrangement=Arrangement.spacedBy(10.dp)){items(fav){p->ProductRow(p,p.id.toString() in cart,true,{cart=flip(cart,p.id.toString());save("cart",cart)},{favorites=flip(favorites,p.id.toString());save("favorites",favorites)})}}}
 else->{Text("حساب کاربری",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold);Spacer(Modifier.height(12.dp));Card(colors=CardDefaults.cardColors(containerColor=SurfaceColor)){Column(Modifier.padding(16.dp)){Text("نسخه مستقل خریدینو");Text("سبد خرید: ${cart.size} محصول");Text("علاقه‌مندی: ${favorites.size} محصول");Text("وضعیت: آفلاین");Text("اطلاعات اولیه روی دستگاه ذخیره می‌شود.")}}}
 }
 }}
}
@Composable private fun ProductRow(p:Product,inCart:Boolean,favorite:Boolean,onCart:()->Unit,onFavorite:()->Unit){
 Card(colors=CardDefaults.cardColors(containerColor=SurfaceColor),shape=RoundedCornerShape(18.dp),modifier=Modifier.fillMaxWidth()){Row(Modifier.padding(12.dp),verticalAlignment=Alignment.CenterVertically){
 Column(Modifier.size(76.dp).background(Color(0xFFE7F3F2),RoundedCornerShape(14.dp)),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.Center){Text("🛍️",style=MaterialTheme.typography.headlineMedium)}
 Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)){Text(p.name,fontWeight=FontWeight.Bold);Text(p.category,color=Color.Gray,style=MaterialTheme.typography.bodySmall);Text(money(p.price),color=Primary,fontWeight=FontWeight.Bold);Button(onClick=onCart){Text(if(inCart)"حذف از سبد" else "افزودن به سبد")}}
 IconButton(onClick=onFavorite){Icon(if(favorite)Icons.Default.Favorite else Icons.Default.FavoriteBorder,contentDescription="علاقه‌مندی",tint=if(favorite)Color.Red else Primary)}
 }}
}