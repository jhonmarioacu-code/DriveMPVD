FROM nginx:1.30.4-alpine@sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46

RUN rm /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/nginx/drivempvd /etc/nginx/includes

COPY docker/nginx/nginx.conf.template /etc/nginx/drivempvd/nginx.conf.template
COPY docker/nginx/http.conf /etc/nginx/drivempvd/http.conf
COPY docker/nginx/https.conf /etc/nginx/drivempvd/https.conf
COPY docker/nginx/locations.conf /etc/nginx/drivempvd/locations.conf
COPY docker/nginx/proxy-headers.conf /etc/nginx/includes/proxy-headers.conf
COPY docker/nginx/security-headers.conf /etc/nginx/includes/security-headers.conf
COPY docker/nginx/40-select-configuration.sh /docker-entrypoint.d/40-select-configuration.sh
COPY docker/nginx/entrypoint.sh /usr/local/bin/drivempvd-nginx-entrypoint.sh

RUN chmod 0555 /docker-entrypoint.d/40-select-configuration.sh \
    /usr/local/bin/drivempvd-nginx-entrypoint.sh

USER nginx

ENTRYPOINT ["/usr/local/bin/drivempvd-nginx-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

EXPOSE 80 443
