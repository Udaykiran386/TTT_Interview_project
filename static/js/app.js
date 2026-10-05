(() => {
  const menuButton = document.querySelector('[data-menu-toggle]');
  const overlay = document.querySelector('[data-menu-close]');

  const setMenuOpen = open => {
    document.body.classList.toggle('menu-open', open);
    if (menuButton) menuButton.setAttribute('aria-expanded', String(open));
  };

  if (menuButton) {
    menuButton.addEventListener('click', () => {
      setMenuOpen(menuButton.getAttribute('aria-expanded') !== 'true');
    });
  }

  if (overlay) overlay.addEventListener('click', () => setMenuOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setMenuOpen(false);
  });

  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
})();
