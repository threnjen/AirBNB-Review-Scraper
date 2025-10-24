If resetting the containers entirely, first prune any old container builds and caches: docker system prune -a --volumes --force 


# Next step if you have reset the cache
docker network create weaviate-network

# Start the Vector Transformer container. These containers rarely need to be deleted/rebuilt.
docker build -f Dockerfiles/Dockerfile.t2v-transformers -t t2v-transformers:latest .

docker run -d --name t2v-transformers --network weaviate-network --env-file weaviate.env t2v-transformers:latest

# Start the Weaviate container. You need to delete the Container and Image if you update the weaviate_client.py
docker build -f Dockerfiles/Dockerfile.weaviate_rag -t weaviate:latest .

docker run -d -p 8080:8080 -p 50051:50051 -v weaviate_data:/var/lib/weaviate -e LOG_LEVEL=debug --name weaviate --env-file weaviate.env --network weaviate-network weaviate:latest




Check docker containers running:

docker container ls

Test open api is working: docker exec -it weaviate sh -c "wget -qO- --header='Authorization: Bearer $OPENAI_API_KEY' https://api.openai.com/v1/models"

docker exec -it weaviate printenv | grep OPENAI

docker logs -f weaviate

curl -v http://localhost:8080/v1/meta

