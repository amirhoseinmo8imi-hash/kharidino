(function () {
  "use strict";

  function productIdFromHref(href) {
    if (!href) return null;
    const match = href.match(/\/product\/(\d+)/);
    return match ? Number(match[1]) : null;
  }

  function fetchInventory(productId) {
    return fetch(`/api/inventory/${productId}`, {
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
      cache: "no-store"
    }).then(function (response) {
      if (!response.ok) throw new Error("inventory request failed");
      return response.json();
    });
  }

  function addBadge(card, info) {
    if (!info || !info.managed || card.querySelector(".ki-inventory-badge")) return;
    const badge = document.createElement("span");
    badge.className = "ki-inventory-badge";
    badge.textContent = info.quantity > 0 ? `موجودی: ${info.quantity} عدد` : "ناموجود";
    card.appendChild(badge);
    if (info.quantity === 0) card.classList.add("ki-out-of-stock");
  }

  function initProductCards() {
    document.querySelectorAll(".km-product").forEach(function (card) {
      const id = productIdFromHref(card.getAttribute("href"));
      if (!id) return;
      fetchInventory(id).then(function (info) {
        addBadge(card, info);
      }).catch(function () {});
    });
  }

  function initProductPage() {
    const match = window.location.pathname.match(/^\/product\/(\d+)/);
    if (!match) return;
    const id = Number(match[1]);
    fetchInventory(id).then(function (info) {
      if (!info || !info.managed) return;
      const stats = document.querySelector(".kd-product-stats");
      if (stats) {
        const item = document.createElement("div");
        item.className = "kd-stat ki-inventory-stat";
        item.innerHTML = '<div class="kd-stat-icon"><i class="fa-solid fa-boxes-stacked"></i></div><div><small>موجودی انبار</small><strong></strong></div>';
        item.querySelector("strong").textContent = info.quantity > 0 ? `${info.quantity} عدد` : "ناموجود";
        stats.appendChild(item);
      }
      const buttons = document.querySelectorAll('form[action*="/cart/add/"] button');
      buttons.forEach(function (button) {
        if (info.quantity <= 0) {
          button.disabled = true;
          button.setAttribute("aria-disabled", "true");
          const text = button.querySelector("span");
          if (text) text.textContent = "ناموجود";
        }
      });
    }).catch(function () {});
  }

  function initCart() {
    document.querySelectorAll(".cart-item[data-product-id]").forEach(function (item) {
      const id = Number(item.getAttribute("data-product-id"));
      if (!id) return;
      const input = item.querySelector(".qty");
      if (!input) return;
      fetchInventory(id).then(function (info) {
        if (!info || !info.managed) return;
        input.max = String(Math.min(99, info.quantity));
        if (Number(input.value) > info.quantity) input.value = String(info.quantity);
        let note = item.querySelector(".ki-inventory-note");
        if (!note) {
          note = document.createElement("small");
          note.className = "ki-inventory-note";
          const box = item.querySelector(".quantity-box");
          if (box) box.appendChild(note);
        }
        if (note) note.textContent = info.quantity > 0 ? `حداکثر ${info.quantity} عدد موجود است` : "این کالا ناموجود است";
        if (info.quantity === 0) {
          input.value = "0";
          input.disabled = true;
          item.classList.add("ki-out-of-stock");
        }
      }).catch(function () {});
    });
  }

  function init() {
    initProductCards();
    initProductPage();
    initCart();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
