/* ============================================================
   ShopEasy — Interactive JavaScript
   ============================================================
   Sections
   1. Toast Notification Engine
   2. Navbar: scroll shadow + mobile hamburger
   3. AJAX Cart: quantity update & item removal
   4. HTML5 Live Form Validation
   5. General UI polish
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {

  /* ----------------------------------------------------------
     1. TOAST NOTIFICATION ENGINE
     Messages are embedded in <script id="django-messages"> as
     JSON by base.html, then rendered as floating toasts.
  ---------------------------------------------------------- */
  const TOAST_DURATION = 5000; // ms before auto-dismiss

  const toastContainer = document.getElementById("toast-container");

  function createToast(message, level = "info") {
    if (!toastContainer) return;

    const levelMap = {
      success : { label: "Success",  cls: "success" },
      error   : { label: "Error",    cls: "error"   },
      warning : { label: "Warning",  cls: "warning" },
      info    : { label: "Info",     cls: "info"    },
      // Django sometimes tags messages without prefix
      debug   : { label: "Info",     cls: "info"    },
    };
    const meta = levelMap[level] || levelMap.info;

    const toast = document.createElement("div");
    toast.className = `toast ${meta.cls}`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    toast.style.position = "relative";

    toast.innerHTML = `
      <span class="toast-icon" aria-hidden="true"></span>
      <div class="toast-body">
        <div class="toast-title">${meta.label}</div>
        <div class="toast-message">${escapeHtml(message)}</div>
      </div>
      <button class="toast-close" aria-label="Dismiss notification">&#x2715;</button>
      <div class="toast-progress" style="animation-duration:${TOAST_DURATION}ms"></div>
    `;

    // Close button
    toast.querySelector(".toast-close").addEventListener("click", () => dismissToast(toast));

    toastContainer.appendChild(toast);

    // Auto-dismiss
    const timer = setTimeout(() => dismissToast(toast), TOAST_DURATION);
    toast._dismissTimer = timer;

    return toast;
  }

  function dismissToast(toast) {
    clearTimeout(toast._dismissTimer);
    toast.classList.add("hiding");
    toast.addEventListener("transitionend", () => toast.remove(), { once: true });
    // Fallback removal if transition doesn't fire
    setTimeout(() => toast.remove(), 500);
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // Parse messages injected by the Django template
  const msgScript = document.getElementById("django-messages");
  if (msgScript) {
    try {
      const messages = JSON.parse(msgScript.textContent || "[]");
      messages.forEach(({ message, level }) => createToast(message, level));
    } catch (e) {
      console.warn("ShopEasy: could not parse django-messages JSON", e);
    }
  }

  // Expose globally so other code can fire toasts too
  window.shopToast = createToast;


  /* ----------------------------------------------------------
     2. NAVBAR: scroll shadow + mobile hamburger
  ---------------------------------------------------------- */
  const navbar = document.querySelector(".navbar");
  const navToggle = document.querySelector(".nav-toggle");
  const navMenu   = document.querySelector(".navbar nav");

  if (navbar) {
    const handleScroll = () => {
      navbar.classList.toggle("scrolled", window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
  }

  if (navToggle && navMenu) {
    navToggle.addEventListener("click", () => {
      const open = navMenu.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open);
      navToggle.textContent = open ? "✕" : "☰";
    });

    // Close menu on outside click
    document.addEventListener("click", (e) => {
      if (!navbar.contains(e.target)) {
        navMenu.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
        navToggle.textContent = "☰";
      }
    });
  }


  /* ----------------------------------------------------------
     3. AJAX CART
     Works by intercepting form submits / link clicks and using
     fetch() to POST/GET the existing Django endpoints, then
     scraping the redirected HTML response for the updated total.
     No backend changes needed.
  ---------------------------------------------------------- */

  // Helpers ------------------------------------------------

  /** Read CSRF token from the cookie Django sets */
  function getCsrfToken() {
    const name = "csrftoken";
    const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : "";
  }

  /** Extract the cart total string from a fetched page HTML */
  function parseTotalFromHtml(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");
    const el = doc.querySelector("[data-cart-total]");
    return el ? el.getAttribute("data-cart-total") : null;
  }

  /** Update the displayed total on the current cart page */
  function updateTotalDisplay(newTotal) {
    const displays = document.querySelectorAll("[data-cart-total]");
    displays.forEach((el) => {
      el.setAttribute("data-cart-total", newTotal);
      el.textContent = newTotal;
    });
  }

  // Quantity update (AJAX form submit) ---------------------
  document.querySelectorAll(".qty-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const cartItem = form.closest(".cart-item");
      const input    = form.querySelector("input[name='quantity']");
      const qty      = parseInt(input ? input.value : 1, 10);
      const action   = form.action;

      if (!action) return;

      // Optimistic UI feedback
      const priceEl = cartItem ? cartItem.querySelector(".cart-item-price") : null;

      try {
        const resp = await fetch(action, {
          method:      "POST",
          credentials: "same-origin",
          redirect:    "follow",
          headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: `quantity=${qty}&csrfmiddlewaretoken=${getCsrfToken()}`,
        });

        if (resp.ok) {
          const html = await resp.text();

          // If qty = 0, animate removal
          if (qty === 0 && cartItem) {
            cartItem.classList.add("removing");
            cartItem.addEventListener("transitionend", () => cartItem.remove(), { once: true });
            setTimeout(() => cartItem.remove(), 500);
          }

          // Update totals scraped from the returned page
          const newTotal = parseTotalFromHtml(html);
          if (newTotal) updateTotalDisplay(newTotal);

          // Update subtotal in the same row if price data available
          if (priceEl && cartItem) {
            const unitPriceStr = cartItem.querySelector("[data-unit-price]")
              ?.getAttribute("data-unit-price");
            if (unitPriceStr) {
              const sub = (parseFloat(unitPriceStr) * qty).toFixed(2);
              priceEl.textContent = `₹${sub}`;
            }
          }
        } else {
          window.shopToast?.("Could not update cart. Please try again.", "error");
        }
      } catch (err) {
        console.error("Cart update failed:", err);
        window.shopToast?.("Network error. Please check your connection.", "error");
      }
    });
  });

  // Stepper buttons (+ / −) --------------------------------
  document.querySelectorAll(".qty-stepper").forEach((stepper) => {
    const input  = stepper.querySelector("input[type=number]");
    const btnDec = stepper.querySelector("[data-action=dec]");
    const btnInc = stepper.querySelector("[data-action=inc]");
    if (!input) return;

    const max = parseInt(input.max || "999", 10);
    const min = parseInt(input.min || "0",   10);

    const fireChange = () => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
    };

    btnDec?.addEventListener("click", () => {
      const cur = parseInt(input.value, 10);
      if (cur > min) { input.value = cur - 1; fireChange(); }
    });

    btnInc?.addEventListener("click", () => {
      const cur = parseInt(input.value, 10);
      if (cur < max) { input.value = cur + 1; fireChange(); }
    });
  });

  // Remove item (AJAX link click) --------------------------
  document.querySelectorAll(".remove-btn[data-remove-url]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      const url      = btn.getAttribute("data-remove-url");
      const cartItem = btn.closest(".cart-item");

      if (!url) return;

      // Animate out immediately for responsiveness
      if (cartItem) {
        cartItem.classList.add("removing");
      }

      try {
        const resp = await fetch(url, {
          method:      "GET",
          credentials: "same-origin",
          redirect:    "follow",
        });

        if (resp.ok) {
          const html  = await resp.text();
          const total = parseTotalFromHtml(html);
          if (total) updateTotalDisplay(total);

          cartItem?.addEventListener("transitionend", () => cartItem.remove(), { once: true });
          setTimeout(() => cartItem?.remove(), 500);
        } else {
          // Rollback animation
          cartItem?.classList.remove("removing");
          window.shopToast?.("Could not remove item. Please try again.", "error");
        }
      } catch (err) {
        cartItem?.classList.remove("removing");
        console.error("Remove failed:", err);
        window.shopToast?.("Network error. Please check your connection.", "error");
      }
    });
  });


  /* ----------------------------------------------------------
     4. HTML5 LIVE FORM VALIDATION
     Targets inputs inside .needs-validation forms.
  ---------------------------------------------------------- */

  /** Rules: field name → { pattern, message } */
  const VALIDATION_RULES = {
    username : { pattern: /^[a-zA-Z0-9_]{3,}$/, message: "At least 3 characters: letters, numbers, underscores." },
    email    : { pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: "Enter a valid email address." },
    phone    : { pattern: /^[0-9+\-\s()]{6,20}$/, message: "Enter a valid phone number." },
    password1: { pattern: /^.{8,}$/, message: "Password must be at least 8 characters." },
    password2: null, // validated against password1 match
  };

  document.querySelectorAll(".needs-validation").forEach((form) => {

    // Real-time validation on input/blur
    form.querySelectorAll("input, textarea").forEach((field) => {
      ["input", "blur"].forEach((evt) => {
        field.addEventListener(evt, () => validateField(field, form));
      });
    });

    // Block submit if invalid
    form.addEventListener("submit", (e) => {
      let formValid = true;
      form.querySelectorAll("input, textarea").forEach((field) => {
        const ok = validateField(field, form);
        if (!ok) formValid = false;
      });
      if (!formValid) {
        e.preventDefault();
        // Shake the submit button
        const btn = form.querySelector("[type=submit]");
        btn?.classList.remove("shake");
        void btn?.offsetWidth; // reflow to restart animation
        btn?.classList.add("shake");
        btn?.addEventListener("animationend", () => btn.classList.remove("shake"), { once: true });
      }
    });
  });

  function validateField(field, form) {
    const name  = field.name;
    const value = field.value.trim();
    const group = field.closest(".form-group");
    let errorEl = group?.querySelector(".field-error");

    // Create error element if it doesn't exist
    if (!errorEl && group) {
      errorEl = document.createElement("span");
      errorEl.className = "field-error";
      group.appendChild(errorEl);
    }

    let valid  = true;
    let errMsg = "";

    // Required check
    if (field.hasAttribute("required") && !value) {
      valid  = false;
      errMsg = "This field is required.";
    }
    // Max length
    else if (field.maxLength > 0 && value.length > field.maxLength) {
      valid  = false;
      errMsg = `Maximum ${field.maxLength} characters allowed.`;
    }
    // Known pattern rules
    else if (VALIDATION_RULES[name]) {
      const rule = VALIDATION_RULES[name];
      if (rule && rule.pattern && !rule.pattern.test(value)) {
        valid  = false;
        errMsg = rule.message;
      }
    }
    // Password confirmation
    else if (name === "password2") {
      const pw1 = form.querySelector("[name=password1]");
      if (pw1 && pw1.value !== field.value) {
        valid  = false;
        errMsg = "Passwords do not match.";
      }
    }

    // Apply UI state
    if (group) {
      group.classList.toggle("has-error", !valid);
    }
    field.classList.toggle("is-invalid", !valid);
    field.classList.toggle("is-valid",    valid && value.length > 0);
    if (errorEl) errorEl.textContent = errMsg;

    return valid;
  }


  /* ----------------------------------------------------------
     5. GENERAL UI POLISH
  ---------------------------------------------------------- */

  // Smooth fade-in for main content
  const mainEl = document.querySelector("main");
  if (mainEl) {
    mainEl.style.opacity = "0";
    mainEl.style.transform = "translateY(10px)";
    mainEl.style.transition = "opacity 0.35s ease, transform 0.35s ease";
    requestAnimationFrame(() => {
      mainEl.style.opacity = "1";
      mainEl.style.transform = "translateY(0)";
    });
  }

  // Auto-mark active nav link based on current path
  const currentPath = window.location.pathname;
  document.querySelectorAll(".navbar nav a").forEach((link) => {
    if (link.getAttribute("href") === currentPath) {
      link.classList.add("active");
    }
  });

  // Product card lazy image fade-in
  if ("IntersectionObserver" in window) {
    const imgObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.opacity = "1";
          imgObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });

    document.querySelectorAll(".card-img-wrap img").forEach((img) => {
      img.style.opacity = "0";
      img.style.transition = "opacity 0.4s ease";
      imgObserver.observe(img);
    });
  }

}); // end DOMContentLoaded
