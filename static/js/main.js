// Live character counter for the tweet composer
document.addEventListener("DOMContentLoaded", () => {
  const textarea = document.querySelector(".composer textarea");
  const counter = document.getElementById("char-count");
  if (textarea && counter) {
    const update = () => {
      counter.textContent = `${textarea.value.length}/280`;
      counter.style.color = textarea.value.length > 260 ? "#f4212e" : "";
    };
    textarea.addEventListener("input", update);
    update();
  }
});
