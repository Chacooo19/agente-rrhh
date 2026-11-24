// Interfaz del asistente de RRHH: login, chat con traza y bandeja de tickets (rol RRHH).
// Sin frameworks ni build: el backend la sirve como archivos estáticos.
"use strict";

const estado = {
  token: sessionStorage.getItem("token"),
  perfil: JSON.parse(sessionStorage.getItem("perfil") || "null"),
  sessionId: null,
  turno: 0,
};

const SUGERENCIAS = {
  empleado: [
    "¿Cuántos días de vacaciones me quedan?",
    "¿Cuánto me toca de aguinaldo este año?",
    "¿Puedo trabajar desde casa?",
    "¿Cuántos días de permiso de paternidad hay?",
  ],
  rrhh: [
    "¿Qué antigüedad tiene E012 y cuántas vacaciones le quedan?",
    "¿Qué tickets están abiertos?",
    "¿Cuál es la política de bonos?",
    "¿Qué dice la LFT sobre la prima vacacional?",
  ],
};

const $ = (sel) => document.querySelector(sel);

function el(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto; // textContent: nunca inyectamos HTML
  return nodo;
}

async function api(ruta, opciones = {}) {
  const cabeceras = { "Content-Type": "application/json" };
  if (estado.token) cabeceras.Authorization = `Bearer ${estado.token}`;
  const r = await fetch(ruta, { ...opciones, headers: cabeceras });
  if (r.status === 401 && estado.token) {
    cerrarSesion();
    throw new Error("Tu sesión expiró. Vuelve a iniciar sesión.");
  }
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : "Ocurrió un error inesperado.";
    throw new Error(detalle);
  }
  return cuerpo;
}

// --- Sesión ------------------------------------------------------------------------------
$("#form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const boton = $("#btn-login");
  const error = $("#error-login");
  boton.disabled = true;
  boton.textContent = "Entrando…";
  error.hidden = true;
  try {
    const datos = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ usuario: $("#usuario").value, password: $("#password").value }),
    });
    estado.token = datos.token;
    estado.perfil = datos;
    sessionStorage.setItem("token", datos.token);
    sessionStorage.setItem("perfil", JSON.stringify(datos));
    mostrarApp();
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    boton.disabled = false;
    boton.textContent = "Entrar";
  }
});

function cerrarSesion() {
  sessionStorage.clear();
  Object.assign(estado, { token: null, perfil: null, sessionId: null, turno: 0 });
  $("#vista-app").hidden = true;
  $("#vista-login").hidden = false;
}
$("#btn-salir").addEventListener("click", cerrarSesion);

function mostrarApp() {
  $("#vista-login").hidden = true;
  $("#vista-app").hidden = false;
  $("#usuario-nombre").textContent = `${estado.perfil.nombre} (${estado.perfil.id_empleado})`;
  $("#usuario-rol").textContent = estado.perfil.rol === "rrhh" ? "RRHH" : "Empleado";
  $("#pestana-tickets").hidden = estado.perfil.rol !== "rrhh";
  nuevaConversacion();
}

// --- Chat --------------------------------------------------------------------------------
function nuevaConversacion() {
  estado.sessionId = null;
  estado.turno = 0;
  $("#mensajes").replaceChildren();
  $("#traza").replaceChildren();
  $("#traza-vacia").hidden = false;
  agregarMensaje(
    "agente",
    `Hola, ${estado.perfil.nombre.split(" ")[0]}. Soy Alta, el asistente de RRHH. ` +
      "Respondo con base en la Ley Federal del Trabajo y el reglamento interno, y te digo de dónde sale cada respuesta.",
  );
  const contenedor = $("#sugerencias");
  contenedor.replaceChildren();
  for (const texto of SUGERENCIAS[estado.perfil.rol] || []) {
    const b = el("button", "", texto);
    b.type = "button";
    b.addEventListener("click", () => enviar(texto));
    contenedor.append(b);
  }
}
$("#btn-nueva").addEventListener("click", nuevaConversacion);

function agregarMensaje(tipo, texto, meta) {
  const burbuja = el("div", `burbuja burbuja--${tipo}`, texto);
  if (meta) burbuja.append(el("div", "burbuja__meta", meta));
  $("#mensajes").append(burbuja);
  burbuja.scrollIntoView({ behavior: "smooth", block: "end" });
  return burbuja;
}

function indicadorEscribiendo() {
  const burbuja = el("div", "burbuja burbuja--agente");
  const puntos = el("span", "escribiendo");
  puntos.append(el("span"), el("span"), el("span"));
  burbuja.append(puntos, el("span", "tenue", "  consultando normativa y datos…"));
  $("#mensajes").append(burbuja);
  burbuja.scrollIntoView({ behavior: "smooth", block: "end" });
  return burbuja;
}

async function enviar(texto) {
  texto = texto.trim();
  if (!texto) return;
  const entrada = $("#mensaje");
  const boton = $("#btn-enviar");
  entrada.value = "";
  boton.disabled = true;
  $("#sugerencias").replaceChildren();
  agregarMensaje("usuario", texto);
  const cargando = indicadorEscribiendo();
  try {
    const r = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ mensaje: texto, session_id: estado.sessionId }),
    });
    estado.sessionId = r.session_id;
    cargando.remove();
    const segundos = (r.latencia_ms / 1000).toFixed(1);
    agregarMensaje("agente", r.respuesta, `${segundos} s · ${r.fuentes.length} fuente(s) consultada(s)`);
    pintarTraza(texto, r);
  } catch (err) {
    cargando.remove();
    agregarMensaje("error", `No se pudo obtener respuesta: ${err.message}`);
  } finally {
    boton.disabled = false;
    entrada.focus();
  }
}

$("#form-chat").addEventListener("submit", (e) => {
  e.preventDefault();
  enviar($("#mensaje").value);
});
$("#mensaje").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    enviar($("#mensaje").value);
  }
});

function pintarTraza(pregunta, r) {
  $("#traza-vacia").hidden = true;
  estado.turno += 1;
  const bloque = el("div", "turno");
  bloque.append(el("h3", "", `Turno ${estado.turno}: “${pregunta.slice(0, 60)}”`));

  for (const alerta of r.alertas) bloque.append(el("div", "aviso", `⚠ ${alerta}`));

  const pasos = r.traza.filter((p) => p.tipo !== "alerta");
  if (pasos.length === 0) bloque.append(el("p", "tenue", "No usó herramientas en este turno."));
  for (const paso of pasos) {
    const detalles = el("details", "paso");
    const icono = paso.tipo === "tool_llamada" ? "→ llamó" : "← resultado";
    detalles.append(el("summary", "", `${icono} ${paso.nombre}`));
    detalles.append(el("pre", "", JSON.stringify(paso.detalle, null, 2)));
    bloque.append(detalles);
  }

  if (r.fuentes.length) {
    const fuentes = el("div");
    fuentes.append(el("div", "tenue", "Fuentes recuperadas:"));
    for (const f of r.fuentes) fuentes.append(el("span", "chip", `${f.fuente} · art. ${f.articulo}`));
    bloque.append(fuentes);
  }
  bloque.append(
    el(
      "div",
      "metricas",
      `${r.modelo} · prompt ${r.version_prompt} · ${r.latencia_ms} ms · ${r.tokens_entrada}+${r.tokens_salida} tokens`,
    ),
  );
  $("#traza").prepend(bloque);
}

// --- Tickets (RRHH) ----------------------------------------------------------------------
document.querySelectorAll(".pestana").forEach((p) =>
  p.addEventListener("click", () => {
    document.querySelectorAll(".pestana").forEach((x) => x.classList.toggle("activa", x === p));
    const vista = p.dataset.vista;
    $("#panel-chat").hidden = vista !== "chat";
    $("#panel-tickets").hidden = vista !== "tickets";
    if (vista === "tickets") cargarTickets();
  }),
);
$("#btn-recargar").addEventListener("click", cargarTickets);

async function cargarTickets() {
  const contenedor = $("#tickets");
  contenedor.replaceChildren(el("p", "tenue", "Cargando…"));
  try {
    const tickets = await api("/api/tickets");
    if (!tickets.length) {
      contenedor.replaceChildren(el("p", "tenue", "No hay tickets todavía."));
      return;
    }
    const tabla = el("table");
    const cabecera = el("tr");
    for (const t of ["Folio", "Empleado", "Asunto", "Detalle", "Prioridad", "Estado", "Creado"]) {
      cabecera.append(el("th", "", t));
    }
    tabla.append(cabecera);
    for (const t of tickets) {
      const fila = el("tr");
      for (const v of [t.folio, t.id_empleado, t.asunto, t.detalle, t.prioridad, t.estado, t.creado_en]) {
        fila.append(el("td", "", String(v)));
      }
      tabla.append(fila);
    }
    contenedor.replaceChildren(tabla);
  } catch (err) {
    contenedor.replaceChildren(el("p", "error", err.message));
  }
}

// Al recargar la página con una sesión válida, entramos directo
if (estado.token && estado.perfil) mostrarApp();
