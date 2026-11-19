/* Симулятор бота «Зерно». Повторяет логику bot/logic.py и bot/handlers.py:
   те же тексты, кнопки и шаги. Как и настоящий бот, правит своё сообщение
   на месте, а не шлёт новое на каждое нажатие. */
(function () {
  "use strict";

  // Копия data/menu.json на случай, когда fetch недоступен (страница открыта через file://).
  var FALLBACK_MENU = {
    shop: "Зерно",
    categories: [
      { id: "coffee", title: "Кофе", items: [
        { id: "espresso", title: "Эспрессо", price: 120 },
        { id: "americano", title: "Американо 0,3", price: 150 },
        { id: "cappuccino", title: "Капучино 0,3", price: 190 },
        { id: "latte", title: "Латте 0,4", price: 210 },
        { id: "raf", title: "Раф ванильный", price: 240 }
      ] },
      { id: "nocoffee", title: "Не кофе", items: [
        { id: "cocoa", title: "Какао 0,3", price: 180 },
        { id: "matcha", title: "Матча латте", price: 230 },
        { id: "tea", title: "Чай улун", price: 130 }
      ] },
      { id: "bakery", title: "Выпечка", items: [
        { id: "croissant", title: "Круассан", price: 150 },
        { id: "roll", title: "Синнабон", price: 170 },
        { id: "cookie", title: "Овсяное печенье", price: 90 }
      ] }
    ]
  };

  var PICKUP_OPTIONS = [10, 20, 30];
  var MAX_QTY = 10;
  var READY_DELAY_MS = 3000;
  var NBSP = " ";

  var TEXT = {
    greeting: "Привет! Это бот кофейни «Зерно».\nСоберите заказ кнопками, а мы приготовим его к вашему приходу.\n\nВыберите раздел меню:",
    menuPrompt: "Выберите раздел меню:",
    pickup: "Когда заберёте заказ?",
    empty: "Корзина пуста. Загляните в меню.",
    cancel: "Корзина очищена. Чтобы начать заново, нажмите /start.",
    staffDone: "\n\nСтатус: готов, клиент получил уведомление."
  };

  var chat = document.getElementById("chat");
  var toastEl = document.getElementById("toast");
  var menu = null;
  var state = { cart: {}, minutes: null };
  var botMsg = null; // сообщение бота, которое правим на месте
  var orderSeq = 147; // следующий заказ будет №148
  var toastTimer = 0;

  // ---------- логика (как в bot/logic.py) ----------
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function price(rub) {
    return String(rub).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP) + NBSP + "₽";
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function hhmm(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function pickupAt(minutes) { return new Date(Date.now() + minutes * 60000); }
  function clampQty(q) { return Math.max(1, Math.min(MAX_QTY, q)); }
  function findCategory(id) { return menu.categories.filter(function (c) { return c.id === id; })[0]; }
  function findItem(id) {
    for (var i = 0; i < menu.categories.length; i++) {
      var items = menu.categories[i].items;
      for (var j = 0; j < items.length; j++) {
        if (items[j].id === id) return { item: items[j], category: menu.categories[i].id };
      }
    }
    return null;
  }
  function cartLines() {
    var lines = [];
    menu.categories.forEach(function (c) {
      c.items.forEach(function (it) {
        var q = state.cart[it.id] || 0;
        if (q > 0) lines.push({ item: it, qty: q, amount: it.price * q });
      });
    });
    return lines;
  }
  function cartTotal() { return cartLines().reduce(function (s, l) { return s + l.amount; }, 0); }
  function cartCount() { return cartLines().reduce(function (s, l) { return s + l.qty; }, 0); }
  function linesBlock() {
    return cartLines().map(function (l) {
      return esc(l.item.title) + " × " + l.qty + " — " + price(l.amount);
    }).join("\n");
  }
  function itemButton(it) { return it.title + " · " + price(it.price); }

  // ---------- отрисовка ----------
  function now() { return hhmm(new Date()); }

  function render(msg, html, rows) {
    var bubble = msg.querySelector(".bubble");
    bubble.innerHTML = html + "<time>" + now() + "</time>";
    var old = msg.querySelector(".kb");
    if (old) old.remove();
    if (rows && rows.length) {
      var kb = document.createElement("div");
      kb.className = "kb";
      rows.forEach(function (row) {
        var r = document.createElement("div");
        r.className = "kb-row";
        row.forEach(function (b) {
          var btn = document.createElement("button");
          btn.type = "button";
          btn.textContent = b.text;
          btn.addEventListener("click", function () { b.run(msg); });
          r.appendChild(btn);
        });
        kb.appendChild(r);
      });
      msg.appendChild(kb);
    }
  }

  function add(kind, html, rows, extraClass) {
    var msg = document.createElement("div");
    msg.className = "msg " + kind + (extraClass ? " " + extraClass : "");
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    msg.appendChild(bubble);
    chat.appendChild(msg);
    render(msg, html, rows);
    scrollDown();
    return msg;
  }

  function edit(html, rows) {
    if (!botMsg) { botMsg = add("in", html, rows); return; }
    var focused = botMsg.contains(document.activeElement);
    render(botMsg, html, rows);
    var bubble = botMsg.querySelector(".bubble");
    bubble.classList.remove("flash");
    void bubble.offsetWidth;
    bubble.classList.add("flash");
    // Кнопки пересоздаются: возвращаем фокус клавиатуры на первую, чтобы не терять место.
    if (focused) {
      var first = botMsg.querySelector(".kb button");
      if (first) first.focus();
    }
    scrollDown();
  }

  function separator(text) {
    var s = document.createElement("div");
    s.className = "sep";
    s.textContent = text;
    chat.appendChild(s);
  }

  function scrollDown() { chat.scrollTop = chat.scrollHeight; }

  function toast(text) {
    toastEl.textContent = text;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 1400);
  }

  function btn(text, run) { return { text: text, run: run }; }

  // ---------- клавиатуры (как в bot/keyboards.py) ----------
  function categoriesKb() {
    return [
      menu.categories.map(function (c) { return btn(c.title, function () { onCategory(c.id); }); }),
      [btn("Корзина", onCart)]
    ];
  }
  function itemsKb(category) {
    var rows = category.items.map(function (it) { return [btn(itemButton(it), function () { onItem(it.id, 1); })]; });
    rows.push([btn("← Меню", onMenu), btn("Корзина", onCart)]);
    return rows;
  }
  function qtyKb(found, qty) {
    var id = found.item.id;
    return [
      [btn("−", function () { onItem(id, qty - 1); }), btn(String(qty), function () {}), btn("+", function () { onItem(id, qty + 1); })],
      [btn("В корзину", function () { onAdd(id, qty); })],
      [btn("← Назад", function () { onCategory(found.category); })]
    ];
  }
  function cartKb(hasItems) {
    if (!hasItems) return [[btn("← Меню", onMenu)]];
    return [[btn("Оформить", onCheckout), btn("Очистить", onClear)], [btn("← Меню", onMenu)]];
  }
  function pickupKb() {
    return [
      PICKUP_OPTIONS.map(function (m) { return btn("Через " + m + " мин", function () { onTime(m); }); }),
      [btn("← Корзина", onCart)]
    ];
  }

  // ---------- обработчики (как в bot/handlers.py) ----------
  function cmdStart() {
    add("out", "/start");
    state = { cart: {}, minutes: null };
    botMsg = add("in", TEXT.greeting, categoriesKb());
  }
  function cmdCancel() {
    add("out", "/cancel");
    state = { cart: {}, minutes: null };
    if (botMsg) render(botMsg, botMsg.querySelector(".bubble").innerHTML.replace(/<time>.*<\/time>$/, ""), []);
    botMsg = null;
    add("in", TEXT.cancel);
  }
  function onCategory(id) {
    var c = findCategory(id);
    edit("<b>" + esc(c.title) + "</b>\nВыберите позицию:", itemsKb(c));
  }
  function onItem(id, qty) {
    var found = findItem(id);
    qty = clampQty(qty);
    edit(
      "<b>" + esc(found.item.title) + "</b>\nЦена: " + price(found.item.price) +
      "\n\nКоличество: " + qty + "\nСумма: " + price(found.item.price * qty),
      qtyKb(found, qty)
    );
  }
  function onAdd(id, qty) {
    var found = findItem(id);
    state.cart[id] = Math.min(MAX_QTY, (state.cart[id] || 0) + clampQty(qty));
    edit(
      "Добавил в корзину: " + esc(found.item.title) + " × " + qty + ".\nВ корзине " +
      cartCount() + " шт. на " + price(cartTotal()),
      [[btn("Добавить ещё", onMenu), btn("Корзина", onCart)]]
    );
    toast("Добавлено");
  }
  function onMenu() { edit(TEXT.menuPrompt, categoriesKb()); }
  function onCart() {
    var has = cartLines().length > 0;
    edit(has ? "<b>Корзина</b>\n" + linesBlock() + "\n\nИтого: <b>" + price(cartTotal()) + "</b>" : TEXT.empty, cartKb(has));
  }
  function onClear() {
    state = { cart: {}, minutes: null };
    edit(TEXT.empty, cartKb(false));
    toast("Корзина очищена");
  }
  function onCheckout() {
    if (!cartLines().length) { toast(TEXT.empty); return; }
    edit(TEXT.pickup, pickupKb());
  }
  function onTime(minutes) {
    state.minutes = minutes;
    edit(
      "<b>Проверьте заказ</b>\n" + linesBlock() + "\n\nИтого: <b>" + price(cartTotal()) + "</b>\n" +
      "Заберёте через " + minutes + " мин, к " + hhmm(pickupAt(minutes)) + ".\nОплата на кассе при получении.",
      [[btn("Подтвердить", onConfirm)], [btn("Изменить время", onCheckout)]]
    );
  }
  function onConfirm() {
    if (!cartLines().length || state.minutes == null) { toast("Заказ устарел, начните заново: /start"); return; }
    var number = ++orderSeq;
    var total = cartTotal();
    var ready = hhmm(pickupAt(state.minutes));
    var lines = linesBlock();
    edit("<b>Заказ №" + number + " принят</b>\nСумма: " + price(total) + "\nБудет готов в " + ready, []);
    toast("Заказ отправлен");
    state = { cart: {}, minutes: null };
    botMsg = null;

    setTimeout(function () { staffMessage(number, lines, total, ready); }, 700);
  }

  // Рабочий чат бариста: в настоящем боте это отдельный чат STAFF_CHAT_ID.
  function staffMessage(number, lines, total, ready) {
    separator("Рабочий чат бариста");
    var done = false;
    var html = "<b>Новый заказ №" + number + "</b>\nКлиент: Гость демо\nВыдать к " + ready +
      "\n\n" + lines + "\n\nИтого: " + price(total);
    var staff = add("in", html, [[btn("Готово", markReady)]], "staff");
    var auto = setTimeout(markReady, READY_DELAY_MS);

    function markReady() {
      if (done) return;
      done = true;
      clearTimeout(auto);
      render(staff, html + '<span class="done-mark">' + TEXT.staffDone + "</span>", []);
      separator("Чат с клиентом");
      add("in", "Заказ №" + number + " готов, заберите на кассе.");
      toast("Клиент получил уведомление");
    }
  }

  // ---------- запуск ----------
  document.querySelectorAll(".cmd").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.dataset.cmd === "/start") cmdStart(); else cmdCancel();
    });
  });

  function demo() {
    // ?demo проигрывает заказ сам: для скриншота в README.
    var steps = [
      function () { onCategory("coffee"); },
      function () { onItem("cappuccino", 1); },
      function () { onAdd("cappuccino", 1); },
      function () { onMenu(); },
      function () { onCategory("bakery"); },
      function () { onItem("croissant", 1); },
      function () { onAdd("croissant", 1); },
      function () { onCart(); },
      function () { onCheckout(); },
      function () { onTime(10); },
      function () { onConfirm(); }
    ];
    steps.forEach(function (fn, i) { setTimeout(fn, 150 * (i + 1)); });
  }

  function start(data) {
    menu = data;
    cmdStart();
    if (/[?&]demo\b/.test(location.search)) {
      document.documentElement.classList.add("demo");
      demo();
    }
  }

  var loaded = false;
  function fallback() { if (!loaded) { loaded = true; start(FALLBACK_MENU); } }
  try {
    fetch("data/menu.json")
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { if (!loaded) { loaded = true; start(data); } })
      .catch(fallback);
  } catch (e) {
    fallback();
  }
})();
