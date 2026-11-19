FROM python:3.13-alpine

# ffmpeg/ffprobe: leer y extraer subtítulos · mkvtoolnix: meter la pista traducida en el mkv
# tesseract: OCR local de subtítulos de imagen y texto grabado (añade más idiomas con tesseract-ocr-data-<código>)
RUN apk add --no-cache ffmpeg mkvtoolnix tzdata tesseract-ocr tesseract-ocr-data-eng tesseract-ocr-data-fra \
    tesseract-ocr-data-spa tesseract-ocr-data-deu tesseract-ocr-data-ita tesseract-ocr-data-por

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY subrr ./subrr

# Usuario sin privilegios (uid 1000). /config escribible por cualquier usuario para que valga el «user:» del compose
# (p. ej. el uid que es dueño de tus vídeos); los volúmenes nuevos heredan estos permisos.
RUN adduser -D -u 1000 subrr && mkdir -p /config && chown subrr:subrr /config && chmod 777 /config
USER subrr

# SUBRR_BIND=0.0.0.0 es necesario dentro de Docker; quien decide qué se publica es el compose («ports:»).
ENV SUBRR_DATA=/config SUBRR_PORT=3007 SUBRR_BIND=0.0.0.0 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 3007
VOLUME /config
HEALTHCHECK --interval=1m --timeout=10s CMD wget -qO- "http://127.0.0.1:${SUBRR_PORT}/salud" || exit 1
CMD ["python", "-m", "subrr"]
