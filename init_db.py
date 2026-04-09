#!/usr/bin/env python3
"""数据库初始化脚本 + 示例题目"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import database


def seed_sample_data():
    """写入示例题目（供测试用）"""
    samples = [
        {
            "source": "Linux", "chapter": "文件与目录", "topic": "文件权限",
            "q_type": "choice",
            "question": "Linux中，用于修改文件权限的命令是？",
            "options": [
                {"letter": "A", "text": "chmod"},
                {"letter": "B", "text": "chown"},
                {"letter": "C", "text": "chgrp"},
                {"letter": "D", "text": "passwd"}
            ],
            "answer": "A",
            "analysis": "chmod 用于修改文件权限，chown 修改所有者，chgrp 修改组。",
            "keywords": "chmod,权限,Linux",
            "difficulty": 2, "dimension": "命令"
        },
        {
            "source": "Linux", "chapter": "进程管理", "topic": "进程查看",
            "q_type": "judge",
            "question": "ps aux 命令可以查看所有用户的进程。",
            "options": [],
            "answer": "true",
            "analysis": "ps aux 列出所有进程，a=所有终端，u=用户导向，x=不受终端控制。",
            "keywords": "ps,进程,Linux",
            "difficulty": 2, "dimension": "命令"
        },
        {
            "source": "MySQL", "chapter": "索引", "topic": "索引类型",
            "q_type": "choice",
            "question": "MySQL 中，B+树索引适用于哪种查询场景？",
            "options": [
                {"letter": "A", "text": "全表扫描"},
                {"letter": "B", "text": "范围查询和排序"},
                {"letter": "C", "text": "随机读取"},
                {"letter": "D", "text": "全文搜索"}
            ],
            "answer": "B",
            "analysis": "B+树索引对范围查询（>、<、BETWEEN）和 ORDER BY 有很好的性能，因为叶子节点是链表连接的。",
            "keywords": "B+树,索引,MySQL",
            "difficulty": 3, "dimension": "原理"
        },
        {
            "source": "MySQL", "chapter": "事务", "topic": "ACID特性",
            "q_type": "fill",
            "question": "MySQL 事务的四大特性ACID分别指：原子性（Atomicity）、______、隔离性（Isolation）、持久性（Durability）。",
            "options": [],
            "answer": "一致性",
            "analysis": "ACID = Atomicity, Consistency, Isolation, Durability。一致性是事务的核心目标。",
            "keywords": "ACID,事务,MySQL",
            "difficulty": 2, "dimension": "原理"
        },
        {
            "source": "Shell", "chapter": "文本处理", "topic": "awk用法",
            "q_type": "choice",
            "question": "awk '{print $2}' file.txt 的作用是？",
            "options": [
                {"letter": "A", "text": "打印文件第2行"},
                {"letter": "B", "text": "打印每行第2个字段"},
                {"letter": "C", "text": "统计第2列之和"},
                {"letter": "D", "text": "删除第2行"}
            ],
            "answer": "B",
            "analysis": "$2 表示每行的第2个字段（列），默认分隔符是空格或Tab。",
            "keywords": "awk,Shell,文本处理",
            "difficulty": 2, "dimension": "命令"
        },
        {
            "source": "高并发", "chapter": "缓存", "topic": "Redis持久化",
            "q_type": "judge",
            "question": "Redis RDB 持久化是阻塞的，会阻塞主线程。",
            "options": [],
            "answer": "false",
            "analysis": "Redis RDB 持久化默认使用 fork() 子进程执行，不阻塞主线程。",
            "keywords": "Redis,RDB,持久化",
            "difficulty": 3, "dimension": "原理"
        },
        {
            "source": "高并发", "chapter": "负载均衡", "topic": "Nginx负载均衡算法",
            "q_type": "choice",
            "question": "Nginx 默认的负载均衡算法是？",
            "options": [
                {"letter": "A", "text": "IP哈希（ip_hash）"},
                {"letter": "B", "text": "最少连接（least_conn）"},
                {"letter": "C", "text": "轮询（round_robin）"},
                {"letter": "D", "text": "加权轮询（weighted）"}
            ],
            "answer": "C",
            "analysis": "Nginx 默认使用轮询（round_robin）算法，每个请求依次分配到不同服务器。",
            "keywords": "Nginx,负载均衡,轮询",
            "difficulty": 2, "dimension": "配置"
        },
        {
            "source": "K8S", "chapter": "Pod", "topic": "Pod生命周期",
            "q_type": "choice",
            "question": "K8S Pod 的状态中，表示所有容器已终止且不会被重启的是哪个？",
            "options": [
                {"letter": "A", "text": "Pending"},
                {"letter": "B", "text": "Running"},
                {"letter": "C", "text": "Succeeded"},
                {"letter": "D", "text": "Failed"}
            ],
            "answer": "C",
            "analysis": "Succeeded 状态表示所有容器成功终止且不会重启（适用于 Job）。",
            "keywords": "Pod,K8S,生命周期",
            "difficulty": 3, "dimension": "原理"
        },
        {
            "source": "K8S", "chapter": "Service", "topic": "Service类型",
            "q_type": "judge",
            "question": "K8S ClusterIP 类型的 Service 只能在集群内部访问。",
            "options": [],
            "answer": "true",
            "analysis": "ClusterIP 是默认类型，仅分配集群内部IP，外部无法直接访问。",
            "keywords": "K8S,Service,ClusterIP",
            "difficulty": 2, "dimension": "配置"
        },
        {
            "source": "Shell", "chapter": "变量与条件", "topic": "Shell条件判断",
            "q_type": "fill",
            "question": "在Bash中，判断文件不存在的条件表达式为：if [ ! -e file ]; then ... fi，其中 -e 表示文件______。",
            "options": [],
            "answer": "存在",
            "analysis": "-e 判断文件是否存在，-f 判断普通文件，-d 判断目录，-r/-w/-x 判断权限。",
            "keywords": "Shell,test,条件判断",
            "difficulty": 2, "dimension": "命令"
        },
        {
            "source": "Linux", "chapter": "用户管理", "topic": "用户权限",
            "q_type": "choice",
            "question": "Linux 系统中，root用户的UID是？",
            "options": [
                {"letter": "A", "text": "0"},
                {"letter": "B", "text": "1"},
                {"letter": "C", "text": "1000"},
                {"letter": "D", "text": "65534"}
            ],
            "answer": "A",
            "analysis": "UID 0 是 root用户的专属UID，普通用户UID通常从1000开始。",
            "keywords": "root,UID,Linux",
            "difficulty": 1, "dimension": "原理"
        },
        {
            "source": "MySQL", "chapter": "SQL基础", "topic": "SELECT语句",
            "q_type": "choice",
            "question": "以下哪个关键字用于对查询结果去重？",
            "options": [
                {"letter": "A", "text": "UNIQUE"},
                {"letter": "B", "text": "DISTINCT"},
                {"letter": "C", "text": "GROUP BY"},
                {"letter": "D", "text": "ORDER BY"}
            ],
            "answer": "B",
            "analysis": "DISTINCT 用于对查询结果去重，UNIQUE 是 Oracle 的语法。",
            "keywords": "DISTINCT,去重,SELECT",
            "difficulty": 2, "dimension": "命令"
        },
        {
            "source": "Shell", "chapter": "循环结构", "topic": "for循环",
            "q_type": "judge",
            "question": "在Bash中，for i in {1..5} 可以遍历1到5的数字。",
            "options": [],
            "answer": "true",
            "analysis": "{1..5} 是Bash的序列表达式，会展开为 1 2 3 4 5。",
            "keywords": "for,循环,Shell",
            "difficulty": 2, "dimension": "命令"
        },
        {
            "source": "高并发", "chapter": "缓存策略", "topic": "缓存穿透",
            "q_type": "choice",
            "question": "缓存穿透是指？",
            "options": [
                {"letter": "A", "text": "大量请求访问一个不存在的key"},
                {"letter": "B", "text": "缓存容量不足导致数据被淘汰"},
                {"letter": "C", "text": "缓存数据过期"},
                {"letter": "D", "text": "缓存服务器宕机"}
            ],
            "answer": "A",
            "analysis": "缓存穿透：大量请求查询一个缓存和数据库都不存在的key，通常用布隆过滤器解决。",
            "keywords": "缓存穿透,布隆过滤器,高并发",
            "difficulty": 3, "dimension": "原理"
        },
        {
            "source": "K8S", "chapter": "ConfigMap", "topic": "配置管理",
            "q_type": "fill",
            "question": "K8S 中，ConfigMap 用于向Pod注入非敏感配置，如果需要注入敏感配置（如密码），应使用______资源。",
            "options": [],
            "answer": "Secret",
            "analysis": "ConfigMap 存非敏感配置，Secret 用于存敏感数据（如密码、token、证书）。",
            "keywords": "ConfigMap,Secret,K8S",
            "difficulty": 2, "dimension": "配置"
        },
    ]

    for s in samples:
        try:
            qid = database.add_question(
                source=s["source"],
                chapter=s["chapter"],
                topic=s.get("topic"),
                q_type=s["q_type"],
                question=s["question"],
                answer=s["answer"],
                options=s.get("options"),
                analysis=s.get("analysis"),
                keywords=s.get("keywords"),
                difficulty=s.get("difficulty", 3),
                dimension=s.get("dimension"),
                score=s.get("score", 10)
            )
            print(f"  [+] [{s['source']}] {s['question'][:30]}... (id={qid})")
        except Exception as e:
            print(f"  [!] 入库失败: {e}")


if __name__ == '__main__':
    print("初始化数据库...")
    database.init_db()
    print("写入示例题目...")
    seed_sample_data()
    print("Done.")
