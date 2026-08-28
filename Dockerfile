FROM maven:3.9.11-eclipse-temurin-21 AS build

WORKDIR /workspace
COPY pom.xml .
COPY libs/ada-observability ./libs/ada-observability
RUN mvn -B -DskipTests dependency:go-offline

COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre

ARG ADA_COMMIT_ID=unknown
ENV ADA_BUILD_COMMIT_ID=${ADA_COMMIT_ID}

WORKDIR /app
RUN useradd --system --create-home --uid 10001 ada
COPY --from=build /workspace/target/ada-*.jar /app/ada.jar
RUN mkdir -p /data && chown -R ada:ada /app /data

USER ada
ENV ADA_DATA_DIR=/data
EXPOSE 8080 8081
ENTRYPOINT ["java", "-jar", "/app/ada.jar"]
