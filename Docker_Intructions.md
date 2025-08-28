docker network create weaviate-network

docker build -f Dockerfiles/Dockerfile.weaviate_rag -t weaviate:latest .

docker build -f Dockerfiles/Dockerfile.t2v-transformers -t t2v-transformers:latest .

docker run -d --name t2v-transformers --network weaviate-network --env-file weaviate.env t2v-transformers:latest

<!-- docker run -d -p 8080:8080 -p 8081:8081 -p 50051:50051 -v weaviate_data:/var/lib/weaviate -e LOG_LEVEL=debug --name weaviate --env-file weaviate.env --network weaviate-network weaviate:latest -->

docker run -d -p 8080:8080 -p 50051:50051 -v weaviate_data:/var/lib/weaviate -e LOG_LEVEL=debug --name weaviate --env-file weaviate.env --network weaviate-network weaviate:latest

<!-- docker build -f Dockerfiles/Dockerfile.rag_description_generation -t rag .

docker run --name rag --env-file weaviate.env --network weaviate-network rag:latest -->



Check docker containers running:

docker container ls

Test open api is working: docker exec -it weaviate sh -c "wget -qO- --header='Authorization: Bearer $OPENAI_API_KEY' https://api.openai.com/v1/models"

docker exec -it weaviate printenv | grep OPENAI

docker logs -f weaviate

curl -v http://localhost:8080/v1/meta

