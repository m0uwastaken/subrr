"""Estilo de la web (copiado de duberr, con otro color de acento), iconos y JS."""

# ------------------------------------------------------------------------------------------------ iconos (trazo 1.6)
_I = {
    'biblio': '<rect x="3" y="4" width="6" height="16" rx="1.5"/><rect x="11" y="4" width="4" height="16" rx="1"/><path d="M17.5 5.5l3 .8-3.6 13.6-3-.8"/>',
    'mas': '<path d="M12 5v14M5 12h14"/>',
    'act': '<path d="M3 12h4l2.5-6 5 12 2.5-6H21"/>',
    'ajustes': '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
    'buscar': '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
    'pausa': '<path d="M9 5v14M15 5v14"/>',
    'play': '<path d="M7 5l12 7-12 7z"/>',
    'papelera': '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    'repetir': '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>',
    'atras': '<path d="M15 6l-6 6 6 6"/>',
    'ok': '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    'aviso': '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.5v.01"/>',
    'x': '<path d="M6 6l12 12M18 6L6 18"/>',
    'bocadillo': '<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-4 3v-3H6a2 2 0 0 1-2-2z"/><path d="M8 9h8M8 12.5h5"/>',
    'motor': '<path d="M5 8h6M8 5v3M6 8c0 4 3 7 6 8M10 8c0 2-1 4-4 6"/><path d="M13 20l4-9 4 9M14.5 17h5"/>',
}


def ic(n, t=18):
    return (f'<svg class="i" width="{t}" height="{t}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_I[n]}</svg>')


LOGO = ('<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="6" fill="var(--acc)"/>'
        '<path d="M6.5 9h11M6.5 12.5h7M6.5 16h9" stroke="var(--acc-tx)" stroke-width="2" stroke-linecap="round"/></svg>')
FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="#4fb6c4"/>'
           '<path d="M6.5 9h11M6.5 12.5h7M6.5 16h9" stroke="#06181b" stroke-width="2" stroke-linecap="round"/></svg>')

CSS = r"""
:root{--bg:#0b0b0d;--s1:#121215;--s2:#18181c;--s3:#202026;--line:#25252b;--line2:#33333b;--tx:#ececef;--tx2:#a3a3ad;--tx3:#6c6c76;
--acc:#4fb6c4;--acc-tx:#06181b;--acc-s:rgba(79,182,196,.13);--ok:#58c48c;--ok-s:rgba(88,196,140,.13);--warn:#e99a4c;--warn-s:rgba(233,154,76,.14);
--err:#ee6b65;--err-s:rgba(238,107,101,.13);--info:#7ea8ff;--info-s:rgba(126,168,255,.13);--sh:0 10px 30px rgba(0,0,0,.35);--r:14px;--r2:9px;color-scheme:dark}
@media (prefers-color-scheme:light){:root{--bg:#f4f3ef;--s1:#fff;--s2:#f8f7f4;--s3:#efede8;--line:#e6e3dc;--line2:#d6d2c9;--tx:#16161a;--tx2:#55555e;--tx3:#8b8b94;
--acc:#167f8d;--acc-tx:#fff;--acc-s:rgba(22,127,141,.1);--ok:#1f8a55;--ok-s:rgba(31,138,85,.1);--warn:#b8641a;--warn-s:rgba(184,100,26,.1);--err:#c63b35;--err-s:rgba(198,59,53,.09);
--info:#2f62d0;--info-s:rgba(47,98,208,.09);--sh:0 8px 24px rgba(30,25,15,.08);color-scheme:light}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 ui-sans-serif,-apple-system,"SF Pro Text","Segoe UI Variable Text","Segoe UI",Roboto,system-ui,sans-serif;
-webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1,"cv11" 1}
a{color:inherit;text-decoration:none}.i{flex:none;display:block}
.top{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:saturate(1.4) blur(14px);-webkit-backdrop-filter:saturate(1.4) blur(14px);border-bottom:1px solid var(--line)}
.top>div{max-width:1080px;margin:0 auto;padding:0 20px;height:58px;display:flex;align-items:center;gap:22px}
.marca{display:flex;align-items:center;gap:9px;font-weight:650;font-size:17px;letter-spacing:-.01em}
.nav{display:flex;gap:4px;margin-left:8px}.pestanas-m{display:none;position:fixed;left:0;right:0;bottom:0;z-index:30;justify-content:space-around;background:color-mix(in srgb,var(--s1) 90%,transparent);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-top:1px solid var(--line);padding:6px 6px calc(6px + env(safe-area-inset-bottom))}.pestanas-m a{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px;font-weight:560;padding:6px 10px;flex:1;color:var(--tx3)}.pestanas-m a.on{color:var(--acc)}.nav a{display:flex;align-items:center;gap:7px;padding:7px 11px;border-radius:8px;color:var(--tx2);font-size:14px;font-weight:550}
.nav a:hover{color:var(--tx);background:var(--s2)}.nav a.on{color:var(--tx);background:var(--s3)}
.vivo{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:13px;color:var(--tx2);min-width:0}
.vivo span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:46vw}
.punto{width:7px;height:7px;border-radius:9px;background:var(--tx3);flex:none}.punto.on{background:var(--acc);animation:latido 1.6s infinite}
@keyframes latido{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--acc) 55%,transparent)}100%{box-shadow:0 0 0 9px transparent}}
main{max-width:1080px;margin:0 auto;padding:26px 20px 90px}
h1{font-size:26px;line-height:1.2;letter-spacing:-.02em;margin:0;font-weight:680}h2{font-size:17px;margin:0;font-weight:640;letter-spacing:-.01em}
.sub{color:var(--tx2);font-size:14px;margin:4px 0 0}.eti{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--tx3);font-weight:600}
.cab{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin:0 0 22px;flex-wrap:wrap}
.seccion{margin:34px 0 12px;display:flex;align-items:center;gap:10px}.seccion .eti{white-space:nowrap}.seccion::after{content:"";flex:1;height:1px;background:var(--line)}
.panel{background:var(--s1);border:1px solid var(--line);border-radius:var(--r)}
.fila{display:grid;grid-template-columns:76px 1fr auto;gap:18px;padding:16px;align-items:start;border-radius:var(--r);transition:background .15s}
a.fila:hover{background:var(--s2)}.lista>*+*{border-top:1px solid var(--line);border-radius:0}.lista>:first-child{border-radius:var(--r) var(--r) 0 0}.lista>:last-child{border-radius:0 0 var(--r) var(--r)}.lista>:only-child{border-radius:var(--r)}
.poster{width:76px;aspect-ratio:2/3;border-radius:7px;background:var(--s3) center/cover;box-shadow:0 0 0 1px var(--line) inset}
.titulo{font-weight:640;font-size:16.5px;letter-spacing:-.01em}.meta{color:var(--tx3);font-size:13px;margin-top:2px}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:3px 9px;border-radius:99px;background:var(--s3);color:var(--tx2);white-space:nowrap}
.badge::before{content:"";width:6px;height:6px;border-radius:9px;background:currentColor}
.b-activo{background:var(--acc-s);color:var(--acc)}.b-aldia{background:var(--ok-s);color:var(--ok)}.b-pausado{color:var(--tx3)}
.cifras{display:grid;grid-template-columns:repeat(3,minmax(0,150px));gap:22px;margin-top:14px}
.cifra .n{font-size:13px;color:var(--tx2);display:flex;justify-content:space-between;gap:8px}.cifra .n b{color:var(--tx);font-weight:600}
.barra{height:3px;border-radius:3px;background:var(--line);margin-top:6px;overflow:hidden}.barra i{display:block;height:100%;border-radius:3px}
.mapa{margin-top:14px;display:grid;gap:5px}.mapa .t{display:flex;align-items:center;gap:8px}.mapa .t>span{font-size:11.5px;color:var(--tx3);width:24px;font-weight:600}
.celdas{display:flex;flex-wrap:wrap;gap:3px}.celdas i{width:11px;height:11px;border-radius:3px;background:var(--line2)}
.e-ok{background:var(--ok)!important}.e-medio{background:var(--acc)!important}.e-ya{background:var(--info)!important}.e-cola{background:var(--warn)!important;opacity:.6}
.e-fallo{background:var(--err)!important}.e-vacio{background:var(--line2)!important}
.leyenda{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--tx3);margin:10px 0 0}.leyenda span{display:flex;align-items:center;gap:6px}.leyenda i{width:9px;height:9px;border-radius:3px;display:block}
.ahora{display:flex;align-items:center;gap:16px;padding:16px 18px;margin-bottom:8px;overflow:hidden;position:relative}
.ahora>.i{color:var(--acc)}.ahora .q{font-weight:600}.ahora .p{color:var(--tx2);font-size:13.5px}
.ahora::after{content:"";position:absolute;left:0;bottom:0;height:2px;width:30%;background:linear-gradient(90deg,transparent,var(--acc),transparent);animation:barrido 2.2s ease-in-out infinite}
@keyframes barrido{0%{left:-30%}100%{left:100%}}
.btn{display:inline-flex;align-items:center;gap:7px;height:36px;padding:0 14px;border-radius:var(--r2);border:1px solid var(--line2);background:var(--s1);color:var(--tx);font:inherit;font-size:13.5px;font-weight:560;cursor:pointer;white-space:nowrap}
.btn:hover{background:var(--s2)}.btn.pri{background:var(--acc);border-color:var(--acc);color:var(--acc-tx)}.btn.pri:hover{filter:brightness(1.06)}
.btn.peligro{color:var(--err)}.btn.peq{height:30px;padding:0 10px;font-size:12.5px}
.btns{display:flex;gap:8px;flex-wrap:wrap;align-items:center}form.in{display:inline}
.vacio{padding:56px 20px;text-align:center}.vacio p{color:var(--tx2);max-width:440px;margin:8px auto 20px}.vacio>.i{margin:0 auto;color:var(--acc)}
.heroe{position:relative;border-radius:var(--r);overflow:hidden;border:1px solid var(--line);background:var(--s1)}
.heroe .fondo{position:absolute;inset:0;background:center/cover;opacity:.22;filter:blur(2px) saturate(1.1);transform:scale(1.04)}
.heroe .fondo::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,var(--s1) 18%,color-mix(in srgb,var(--s1) 55%,transparent))}
.heroe>.cont{position:relative;display:grid;grid-template-columns:132px 1fr;gap:24px;padding:24px}
.heroe .poster{width:132px}.volver{display:inline-flex;align-items:center;gap:4px;color:var(--tx2);font-size:13.5px;margin-bottom:14px}.volver:hover{color:var(--tx)}
table{width:100%;border-collapse:collapse}th{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);font-weight:600;text-align:left;padding:10px 14px;border-bottom:1px solid var(--line)}
td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:middle;font-size:14px}
td.num{color:var(--tx3);font-weight:600;width:56px;font-size:13px}.ept{font-weight:540}.ept small{display:block;color:var(--tx3);font-size:12.5px;font-weight:400}
.estado{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--tx2);white-space:nowrap}.estado i{width:8px;height:8px;border-radius:3px;display:block}
details.ep>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:64px 1fr auto;gap:14px;align-items:center;padding:12px 16px}
details.ep>summary::-webkit-details-marker{display:none}details.ep>summary:hover{background:var(--s2)}details.ep+details.ep{border-top:1px solid var(--line)}
details.ep .num{color:var(--tx3);font-weight:600;font-size:13px}
.desp{padding:4px 16px 18px;color:var(--tx2);font-size:13.5px}.desp .kv{display:grid;grid-template-columns:150px 1fr;gap:4px 14px;margin:8px 0 14px}.desp .kv b{color:var(--tx3);font-weight:500}
.mono{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:12.5px}
.muestra{display:grid;grid-template-columns:70px 1fr 1fr;gap:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:6px 0 14px;font-size:13px}
.muestra>div{padding:7px 10px;border-top:1px solid var(--line)}.muestra>div:nth-child(-n+3){border-top:0;background:var(--s2);font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--tx3);font-weight:600}
.muestra .t{color:var(--tx3)}.muestra .es{color:var(--tx)}
.grupo{padding:20px 22px}.grupo+.grupo{border-top:1px solid var(--line)}.grupo h3{margin:0;font-size:15px;font-weight:640}.grupo>p{margin:3px 0 14px;color:var(--tx3);font-size:13px}
.campo{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:20px;padding:12px 0;align-items:center}.campo+.campo{border-top:1px dashed var(--line)}
.campo label{font-weight:560;font-size:14px}.campo .ay{color:var(--tx3);font-size:12.8px;margin-top:2px;line-height:1.45}
select,input[type=search],input[type=text]{width:100%;height:36px;border-radius:var(--r2);border:1px solid var(--line2);background:var(--s2);color:var(--tx);font:inherit;font-size:14px;padding:0 11px}
select{appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23888' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 11px center;padding-right:30px}
select:focus,input:focus{outline:2px solid color-mix(in srgb,var(--acc) 50%,transparent);outline-offset:1px}
.interruptor{position:relative;display:inline-block;width:40px;height:24px;flex:none;vertical-align:middle}.interruptor input{opacity:0;position:absolute;inset:0;margin:0;cursor:pointer;z-index:1}
.interruptor i{position:absolute;inset:0;border-radius:20px;background:var(--line2);transition:.15s}.interruptor i::after{content:"";position:absolute;width:18px;height:18px;left:3px;top:3px;border-radius:20px;background:#fff;transition:.15s}
.interruptor input:checked+i{background:var(--acc)}.interruptor input:checked+i::after{left:19px}
.herram{display:flex;gap:10px;align-items:center;margin-bottom:18px;flex-wrap:wrap}.herram .busca{position:relative;flex:1;min-width:220px}
.herram .busca .i{position:absolute;left:11px;top:9px;color:var(--tx3)}.herram .busca input{padding-left:36px}
.pestanas{display:inline-flex;background:var(--s2);border:1px solid var(--line);border-radius:10px;padding:3px}.pestanas button{border:0;background:none;color:var(--tx2);font:inherit;font-size:13.5px;font-weight:560;padding:6px 14px;border-radius:7px;cursor:pointer}
.pestanas button.on{background:var(--s1);color:var(--tx);box-shadow:0 1px 2px rgba(0,0,0,.25)}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:22px 16px}
.tarjeta{cursor:pointer;background:none;border:0;padding:0;text-align:left;color:inherit;font:inherit}.tarjeta .poster{width:100%;border-radius:10px;transition:transform .2s,box-shadow .2s;position:relative}
.tarjeta:hover .poster{transform:translateY(-2px);box-shadow:var(--sh),0 0 0 1px var(--line) inset}.tarjeta b{display:block;font-size:14px;font-weight:600;margin-top:9px;line-height:1.3}
.tarjeta span{font-size:12.5px;color:var(--tx3)}.tarjeta .marca-d{position:absolute;top:8px;right:8px;background:var(--acc);color:var(--acc-tx);border-radius:99px;padding:2px 8px;font-size:11px;font-weight:700}
dialog{border:1px solid var(--line2);border-radius:16px;background:var(--s1);color:var(--tx);padding:0;width:min(460px,calc(100vw - 32px));box-shadow:0 30px 80px rgba(0,0,0,.5)}
dialog::backdrop{background:rgba(0,0,0,.55);backdrop-filter:blur(3px)}dialog .dc{padding:22px}dialog .pie{display:flex;justify-content:flex-end;gap:8px;padding:14px 22px;border-top:1px solid var(--line);background:var(--s2)}
.temps{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin:16px 0 4px}.temps label{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid var(--line2);border-radius:var(--r2);cursor:pointer;font-size:14px}
.temps label:has(input:checked){border-color:var(--acc);background:var(--acc-s)}.temps input{accent-color:var(--acc);width:16px;height:16px;margin:0}.temps small{margin-left:auto;color:var(--tx3);font-size:12px}
.nota{display:flex;gap:12px;padding:14px 16px;font-size:13.5px;color:var(--tx2);margin-bottom:22px}.nota .i{color:var(--acc);margin-top:2px}.nota b{color:var(--tx)}
.act{display:grid;grid-template-columns:28px 1fr auto;gap:12px;padding:13px 16px;align-items:start}.act .ico{width:28px;height:28px;border-radius:8px;display:grid;place-items:center}
.act .ico.ok{background:var(--ok-s);color:var(--ok)}.act .ico.ko{background:var(--err-s);color:var(--err)}.act .q{font-size:14px}.act .q b{font-weight:600}
.act .d{font-size:12.8px;color:var(--tx3);margin-top:2px;word-break:break-word}.act .h{font-size:12.5px;color:var(--tx3);white-space:nowrap}
.dia{margin:26px 0 8px}.filtros{display:flex;gap:6px}.filtros a{padding:6px 12px;border-radius:99px;font-size:13px;color:var(--tx2);border:1px solid var(--line)}.filtros a.on{background:var(--tx);color:var(--bg);border-color:var(--tx)}
.aviso{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:var(--r2);background:var(--warn-s);color:var(--warn);font-size:13.5px;margin-top:12px}
.aviso.err{background:var(--err-s);color:var(--err)}.aviso.ok{background:var(--ok-s);color:var(--ok)}
.datos{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border-radius:var(--r);overflow:hidden;border:1px solid var(--line);margin-bottom:8px}
.datos>div{background:var(--s1);padding:14px 16px}.datos b{display:block;font-size:22px;font-weight:650;letter-spacing:-.02em}.datos span{font-size:12.5px;color:var(--tx3)}
.motores{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:22px}.motores .panel{padding:16px 18px}.motores .barra{height:5px;margin:10px 0 6px}
.cargando{color:var(--tx3);font-size:13px;padding:8px 0}
@media (max-width:760px){
 .top>div{height:52px;padding:0 16px}.top .nav{display:none}.pestanas-m{display:flex}
 main{padding:20px 16px 110px}h1{font-size:23px}.fila{grid-template-columns:56px 1fr;gap:14px;padding:14px}.poster{width:56px}.fila>.der{grid-column:1/-1;display:none}
 .cifras{grid-template-columns:repeat(3,1fr);gap:12px}.heroe>.cont{grid-template-columns:84px 1fr;gap:16px;padding:18px}.heroe .poster{width:84px}
 .campo{grid-template-columns:1fr;gap:8px}.datos{grid-template-columns:repeat(2,1fr)}.motores{grid-template-columns:1fr}
 .rejilla{grid-template-columns:repeat(3,1fr);gap:16px 10px}.tarjeta b{font-size:12.5px}.oc-m{display:none}
 details.ep>summary{grid-template-columns:52px 1fr;padding:12px}details.ep>summary .estado{grid-column:2}
 .desp .kv{grid-template-columns:1fr}.vivo span{max-width:52vw}.muestra{grid-template-columns:1fr 1fr}.muestra .t{display:none}
}
"""

JS = r"""
const $=(s,e=document)=>e.querySelector(s),$$=(s,e=document)=>[...e.querySelectorAll(s)];
async function vivo(){try{const r=await fetch('/api/vivo');const v=await r.json();const t=$('#vivo-t'),p=$('#vivo-p');
 if(v.trabajando){t.textContent=v.trabajando+(v.paso?' · '+v.paso:'');p.classList.add('on')}else{t.textContent=v.cola?`${v.cola} en cola`:'En espera'+(v.ultima_pasada?' · '+v.ultima_pasada:'');p.classList.remove('on')}
 const a=$('#ahora');if(a){if(v.trabajando){a.hidden=false;$('.q',a).textContent=v.trabajando;$('.p',a).textContent=v.paso||''}else{if(!a.hidden)location.reload()}}
}catch(e){}}
setInterval(vivo,4000);vivo();
document.addEventListener('submit',e=>{const m=e.target.dataset.confirmar;if(m&&!confirm(m))e.preventDefault()});
document.addEventListener('click',e=>{const b=e.target.closest('[data-abrir]');if(b){const d=document.getElementById(b.dataset.abrir);d&&d.showModal()}
 const c=e.target.closest('[data-cerrar]');if(c){c.closest('dialog').close()}});
document.addEventListener('toggle',async e=>{const d=e.target;if(!d.matches||!d.matches('details.ep')||!d.open||d.dataset.ok)return;d.dataset.ok=1;
 const box=$('.desp',d);try{const r=await fetch(`/api/ep?k=${encodeURIComponent(d.dataset.k)}&c=${d.dataset.c}`);box.innerHTML=await r.text()}catch(x){box.textContent='No se pudo cargar.'}},true);
const busca=$('#busca');if(busca){const f=()=>{const q=busca.value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');const tab=$('.pestanas .on')?.dataset.tab;
 $$('.tarjeta').forEach(t=>{t.hidden=!(t.dataset.n.includes(q)&&(!tab||t.dataset.tipo===tab))})};busca.addEventListener('input',f);
 $$('.pestanas button').forEach(b=>b.addEventListener('click',()=>{$$('.pestanas button').forEach(x=>x.classList.remove('on'));b.classList.add('on');f()}));f()}
"""



_I.update({
    'arriba': '<path d="M6 15l6-6 6 6"/>',
    'abajo': '<path d="M6 9l6 6 6-6"/>',
    'enchufe': '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
    'editar': '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/>',
    'prueba': '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/>',
})

CSS += r"""
.subnav{display:flex;gap:6px;margin:0 0 20px;flex-wrap:wrap}.subnav a{padding:7px 14px;border-radius:99px;font-size:13.5px;font-weight:560;color:var(--tx2);border:1px solid var(--line)}
.subnav a.on{background:var(--tx);color:var(--bg);border-color:var(--tx)}
textarea{width:100%;min-height:76px;border-radius:var(--r2);border:1px solid var(--line2);background:var(--s2);color:var(--tx);font:inherit;font-size:13.5px;padding:9px 11px;resize:vertical}
input[type=password],input[type=number]{width:100%;height:36px;border-radius:var(--r2);border:1px solid var(--line2);background:var(--s2);color:var(--tx);font:inherit;font-size:14px;padding:0 11px}
.motor{display:grid;grid-template-columns:auto 1fr auto;gap:14px;padding:14px 16px;align-items:center}.motor+.motor{border-top:1px solid var(--line)}
.motor .orden{display:flex;flex-direction:column;gap:2px}.motor .orden button{border:1px solid var(--line2);background:var(--s1);color:var(--tx2);border-radius:6px;width:28px;height:22px;display:grid;place-items:center;cursor:pointer;padding:0}
.motor .orden button:disabled{opacity:.3;cursor:default}.motor .n{font-weight:600}.motor .m{font-size:12.8px;color:var(--tx3);margin-top:2px}
.pildora{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 8px;border-radius:99px;background:var(--s3);color:var(--tx2);margin-left:6px}
.pildora.res{background:var(--warn-s);color:var(--warn)}.pildora.off{color:var(--tx3)}.pildora.pri{background:var(--acc-s);color:var(--acc)}
.prueba-ok{color:var(--ok)}.prueba-ko{color:var(--err)}
.conex{display:grid;grid-template-columns:150px 1fr 1fr auto;gap:10px;align-items:center;padding:12px 0}.conex+.conex{border-top:1px dashed var(--line)}
.conex .estado-c{font-size:12.8px}
@media (max-width:760px){.conex{grid-template-columns:1fr}.motor{grid-template-columns:auto 1fr}.motor>.btns{grid-column:1/-1}}
"""

JS += r"""
document.addEventListener('click',async e=>{const b=e.target.closest('[data-probar]');if(!b)return;e.preventDefault();const out=document.getElementById(b.dataset.out);
 out.className='';out.textContent='Probando…';try{const r=await fetch(b.dataset.probar,{method:'POST'});const j=await r.json();out.className=j.ok?'prueba-ok':'prueba-ko';out.textContent=(j.ok?'✓ ':'✗ ')+j.texto}catch(x){out.className='prueba-ko';out.textContent='✗ '+x}});
"""
