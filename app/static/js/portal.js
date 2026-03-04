/* ═══ WON-DOOR PORTAL — JS ═══ */

// Mobile drawer
function toggleDrawer(){
  document.getElementById('mDrawer').classList.toggle('open');
  document.getElementById('mOverlay').classList.toggle('open');
}

// Theme toggle
function toggleTheme(){
  const html = document.documentElement;
  const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  // Persist via API
  fetch('/api/theme', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({theme:next})});
}

// Close avatar dropdown on outside click
document.addEventListener('click', function(e){
  document.querySelectorAll('.avatar-dropdown.open').forEach(function(el){
    if(!el.contains(e.target)) el.classList.remove('open');
  });
});

// Auto-dismiss toasts
document.addEventListener('DOMContentLoaded', function(){
  document.querySelectorAll('.toast.show').forEach(function(t){
    setTimeout(function(){ t.classList.remove('show'); }, 4000);
  });
});
