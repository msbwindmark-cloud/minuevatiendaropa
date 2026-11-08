(function () {
  "use strict";

  function getCookie(name) {
    let value = null;
    if (document.cookie) {
      document.cookie.split(";").forEach((c) => {
        const [k, v] = c.trim().split("=");
        if (k === name) value = decodeURIComponent(v || "");
      });
    }
    return value;
  }

  window.bosselliApi = async function (url, options = {}) {
    const headers = Object.assign(
      { "X-CSRFToken": getCookie("csrftoken"), "X-Requested-With": "XMLHttpRequest" },
      options.headers || {}
    );
    const res = await fetch(url, Object.assign({ credentials: "same-origin", headers }, options));
    if (!res.ok) throw new Error("HTTP " + res.status);
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
  };

  window.confirmar = function (mensaje, texto) {
    if (window.Swal) {
      return Swal.fire({
        title: "¿Seguro?",
        text: mensaje,
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Sí, continuar",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#0f172a",
        cancelButtonColor: "#78716c",
      }).then((r) => r.isConfirmed);
    }
    return Promise.resolve(window.confirm(mensaje || texto || "¿Seguro?"));
  };

  document.addEventListener("DOMContentLoaded", function () {
    // Auto-cierre de mensajes
    document.querySelectorAll(".alert-dismissible").forEach((el) => {
      setTimeout(() => {
        if (window.bootstrap && window.bootstrap.Alert) {
          window.bootstrap.Alert.getOrCreateInstance(el).close();
        }
      }, 7000);
    });

    // Tooltips
    if (window.bootstrap && window.bootstrap.Tooltip) {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
        new window.bootstrap.Tooltip(el);
      });
    }

    // Confirmación de borrado
    document.querySelectorAll("form[data-confirm]").forEach((form) => {
      form.addEventListener("submit", function (e) {
        if (form.dataset.confirmed === "1") return;
        e.preventDefault();
        window.confirmar(form.dataset.confirm).then((ok) => {
          if (ok) {
            form.dataset.confirmed = "1";
            form.submit();
          }
        });
      });
    });

    // Cálculo automático base + IVA -> total
    document.querySelectorAll("[data-total-form]").forEach((form) => {
      const base = form.querySelector('[name="base"]');
      const iva = form.querySelector('[name="iva_pct"]');
      const total = form.querySelector('[name="total"]');
      if (!base || !iva || !total) return;
      const recalcular = () => {
        const b = parseFloat(String(base.value).replace(",", ".")) || 0;
        const i = parseFloat(String(iva.value).replace(",", ".")) || 0;
        if (b > 0 && document.activeElement !== total) {
          total.value = (b * (1 + i / 100)).toFixed(2);
        }
      };
      base.addEventListener("input", recalcular);
      iva.addEventListener("change", recalcular);
    });

    // Búsqueda automática con retardo
    document.querySelectorAll("[data-auto-search]").forEach((input) => {
      let t = null;
      input.addEventListener("input", () => {
        clearTimeout(t);
        t = setTimeout(() => {
          if (input.form) input.form.submit();
        }, 450);
      });
    });

    // Mostrar/ocultar contraseña
    document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = document.querySelector(btn.dataset.togglePassword);
        if (!input) return;
        const tipo = input.getAttribute("type") === "password" ? "text" : "password";
        input.setAttribute("type", tipo);
        const icon = btn.querySelector("i");
        if (icon) {
          icon.classList.toggle("bi-eye");
          icon.classList.toggle("bi-eye-slash");
        }
      });
    });

    // PWA
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch(() => {});
      });
    }
  });
})();
