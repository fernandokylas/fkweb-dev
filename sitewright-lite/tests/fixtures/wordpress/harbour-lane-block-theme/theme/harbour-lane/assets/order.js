// Harbour Lane Bakery order form [fixture]: a SIMULATED handler. The delivery endpoint is
// unknown (OPEN-2), so nothing is sent. Review states with ?state=loading|error|success.
(function () {
  "use strict";
  var form = document.getElementById("order-form");
  if (!form) return;
  var status = document.getElementById("order-status");
  var submit = form.querySelector('button[type="submit"]');
  var MIN_NOTICE_DAYS = 3;

  function fieldError(id, message) {
    var input = document.getElementById(id);
    var slot = document.getElementById(id + "-error");
    if (message) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
    slot.textContent = message || "";
  }

  function validate(data) {
    var errors = {};
    if (!data.name.trim()) errors.name = "Enter your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email.trim())) errors.email = "Enter an email address like name@example.org.";
    if (!data.cake) errors.cake = "Choose a cake.";
    if (!data.date) {
      errors.date = "Choose a collection date.";
    } else {
      var earliest = new Date();
      earliest.setHours(0, 0, 0, 0);
      earliest.setDate(earliest.getDate() + MIN_NOTICE_DAYS);
      if (new Date(data.date + "T00:00:00") < earliest) errors.date = "Choose a date at least three days from today.";
    }
    return errors;
  }

  function setState(state, content) {
    status.setAttribute("data-state", state);
    status.replaceChildren();
    if (content) status.append.apply(status, content);
    form.setAttribute("aria-busy", state === "loading" ? "true" : "false");
    submit.disabled = state === "loading";
  }

  function el(tag, text, attrs) {
    var node = document.createElement(tag);
    if (text) node.textContent = text;
    for (var k in attrs || {}) node.setAttribute(k, attrs[k]);
    return node;
  }

  function showErrors(errors) {
    ["name", "email", "cake", "date"].forEach(function (id) { fieldError(id, errors[id]); });
    var ids = Object.keys(errors);
    var list = el("ul");
    ids.forEach(function (id) {
      var item = el("li");
      item.append(el("a", errors[id], { href: "#" + id }));
      list.append(item);
    });
    setState("error", [el("p", ids.length === 1 ? "There is a problem with 1 field:" : "There are problems with " + ids.length + " fields:"), list]);
    document.getElementById(ids[0]).focus();
  }

  function showSuccess(data) {
    var summary = el("dl");
    [["Name", data.name], ["Email", data.email], ["Cake", data.cake], ["Collection date", data.date]].forEach(function (pair) {
      summary.append(el("dt", pair[0]), el("dd", pair[1]));
    });
    var back = el("p");
    back.append(el("a", "Back to the menu", { href: "/menu/" }));
    setState("success", [el("p", "Order enquiry recorded (simulated, nothing was sent).", {}), summary, back]);
    status.setAttribute("tabindex", "-1");
    status.focus();
  }

  function read() {
    return {
      name: form.elements.name.value, email: form.elements.email.value,
      cake: form.elements.cake.value, date: form.elements.date.value
    };
  }

  form.setAttribute("novalidate", "");
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var data = read();
    var errors = validate(data);
    if (Object.keys(errors).length) return showErrors(errors);
    ["name", "email", "cake", "date"].forEach(function (id) { fieldError(id); });
    setState("loading", [el("p", "Sending your order enquiry…")]);
    window.setTimeout(function () { showSuccess(data); }, 600);
  });

  // Review flags: show a state without filling the form. Not linked from any page.
  var flag = new URLSearchParams(window.location.search).get("state");
  var sample = { name: "Sam Rivers", email: "sam@harbourlane.test", cake: "Victoria sponge, serves 12", date: "2026-10-20" };
  if (flag === "loading") setState("loading", [el("p", "Sending your order enquiry…")]);
  else if (flag === "error") showErrors({ email: "Enter an email address like name@example.org.", date: "Choose a collection date." });
  else if (flag === "success") showSuccess(sample);
})();
