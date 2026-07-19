FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/nginx/drivempvd /etc/nginx/includes

COPY docker/nginx/nginx.conf.template /etc/nginx/drivempvd/nginx.conf.template
COPY docker/nginx/http.conf /etc/nginx/drivempvd/http.conf
COPY docker/nginx/https.conf /etc/nginx/drivempvd/https.conf
COPY docker/nginx/locations.conf /etc/nginx/drivempvd/locations.conf
COPY docker/nginx/proxy-headers.conf /etc/nginx/includes/proxy-headers.conf
COPY docker/nginx/security-headers.conf /etc/nginx/includes/security-headers.conf
COPY docker/nginx/40-select-configuration.sh /docker-entrypoint.d/40-select-configuration.sh

RUN chmod 0555 /docker-entrypoint.d/40-select-configuration.sh

EXPOSE 80 443
