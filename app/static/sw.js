const CACHE="pharmaamr-shell-v1";
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(["/static/style.css","/static/app.js","/static/manifest.json"]))));
self.addEventListener("fetch",e=>{
  if(e.request.method!=="GET") return;
  const url=new URL(e.request.url);
  if(url.origin===location.origin && url.pathname.startsWith("/static/")){
    e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
  }
});
