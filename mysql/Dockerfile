# Farm Bridge — MySQL service image for Render.
#
# Render's managed databases are PostgreSQL-only, so MySQL runs as a private
# service built from the official MySQL 8 image. The image initialises the
# database + user from MYSQL_DATABASE / MYSQL_USER / MYSQL_PASSWORD /
# MYSQL_ROOT_PASSWORD (set in render.yaml), and data lives on a persistent
# disk mounted at /var/lib/mysql.
FROM mysql:8.0
