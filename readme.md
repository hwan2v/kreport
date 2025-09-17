#### 버전
opensearch 2.17.1
python 3.11




## 초기 설정


```
# wsl ubuntu

sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p || true
```

## 아이디어

색인
  색인을 api로만 받나? docker-compose에서 worker(celery)를 통해 주기적으로 호출하면 안돼?
  배치?
  
확장성
  k8s 기반의 메니페스트도 작성?
  argo도 작성? 너무 오바야?

로그
  로그스태시로 처리할까? 비동기
  mkdir -p logstash/pipeline
  mkdir -p logs

보안
  api-key를 발급받어?
  opensearch ssl 적용해? 과연 필요할까?

속도 측정
  단일 쿼리/평균 쿼리

품질
  ndcg 넣어? 어떻게 해?

스키마

