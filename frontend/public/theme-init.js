(function () {
  var root = document.documentElement;
  var dark = false;
  try {
    var preference = window.localStorage.getItem('ecommerce.theme');
    dark =
      preference === 'dark' ||
      (preference !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  } catch (error) {
    dark = false;
  }
  root.classList.toggle('dark', dark);
  root.style.colorScheme = dark ? 'dark' : 'light';
})();
