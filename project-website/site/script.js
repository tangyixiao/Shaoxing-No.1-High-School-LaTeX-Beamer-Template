"use strict";

// Navigation and the native language picker also work without JavaScript.
document.documentElement.classList.add("js");

const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector(".main-nav");

if (menuButton && navigation) {
  menuButton.hidden = false;

  const setOpen = (open) => {
    navigation.classList.toggle("is-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    const label = open ? menuButton.dataset.closeLabel : menuButton.dataset.openLabel;
    if (label) menuButton.setAttribute("aria-label", label);
  };

  menuButton.addEventListener("click", () => {
    setOpen(menuButton.getAttribute("aria-expanded") !== "true");
  });

  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) setOpen(false);
  });

  // Only consume Escape here after an open picker has had a chance to close.
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (document.querySelector(".picker[open]")) return;
    if (menuButton.getAttribute("aria-expanded") !== "true") return;
    setOpen(false);
    menuButton.focus();
  });
}

const pickers = [...document.querySelectorAll("details.picker")];
pickers.forEach((picker) => {
  picker.addEventListener("toggle", () => {
    if (!picker.open) return;
    pickers.forEach((other) => { if (other !== picker) other.open = false; });
  });
});

document.addEventListener("click", (event) => {
  pickers.forEach((picker) => {
    if (!picker.contains(event.target)) picker.open = false;
  });
});

// Capture lets Escape close a picker before the mobile navigation handler.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const openPicker = pickers.find((picker) => picker.open);
  if (!openPicker) return;
  openPicker.open = false;
  openPicker.querySelector("summary").focus();
  event.preventDefault();
}, true);

const themePicker = document.querySelector(".theme-picker");
const theme = window.ProjectTheme;
if (themePicker && theme) {
  const themeButtons = [...themePicker.querySelectorAll("button[data-theme-choice]")];
  const currentLabel = themePicker.querySelector(".theme-current");
  const updateThemePicker = () => {
    const selected = theme.getChoice();
    const mode = document.documentElement.dataset.colorMode;
    themePicker.dataset.mode = mode;
    document.querySelectorAll("a[data-light-href][data-dark-href]").forEach((link) => {
      link.setAttribute("href", mode === "dark" ? link.dataset.darkHref : link.dataset.lightHref);
    });
    themeButtons.forEach((button) => {
      const active = button.dataset.themeChoice === selected;
      button.setAttribute("aria-pressed", String(active));
      if (active && currentLabel) {
        const label = button.querySelector("span");
        currentLabel.textContent = (label || button).textContent.trim();
      }
    });
  };
  themePicker.hidden = false;
  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      theme.setChoice(button.dataset.themeChoice);
      themePicker.open = false;
      themePicker.querySelector("summary").focus();
    });
  });
  document.addEventListener("project-theme-change", updateThemePicker);
  updateThemePicker();
}
