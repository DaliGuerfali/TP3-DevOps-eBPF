# Présenter le TP eBPF en 5 minutes

**Équipe :** Mohamed Ali Guerfali · Alaeddine Zaouali · Rami Gharbi · Adem Saidi
**Support :** le PDF `Compte-rendu-TP-eBPF-Guerfali-Zaouali-Gharbi-Saidi.pdf` (projeté), plus Grafana en direct si possible.

**Le message à faire passer en une phrase :**
> Sans toucher au code, eBPF nous donne les métriques RED côté serveur ET côté client. Cela suffit pour trouver où part le temps, qui cause les erreurs, et à quel débit le système s'effondre.

---

## Déroulé minuté

| Temps | Qui | Partie | À l'écran |
|---|---|---|---|
| 0:00 – 1:00 | Mohamed Ali | Contexte, architecture, comment eBPF intercepte | Page 1, Figure 1 |
| 1:00 – 2:00 | Alaeddine | Mise en œuvre et fiabilité des mesures | Page 1 (§2), puis tableau page 2 |
| 2:00 – 3:15 | Rami | Décomposition de latence, erreurs, tail latency (Q1) | Page 2 (§4), page 3 |
| 3:15 – 4:30 | Adem | Saturation CPU, loi de Little (Q2) | Page 4 |
| 4:30 – 5:00 | Mohamed Ali | Conclusion, trois leçons | Page 4 (§8) |

La répartition est une proposition : échangez les rôles si besoin, mais gardez les durées.

---

### 1. Mohamed Ali : contexte et eBPF (1 min)

- « Nous avons une chaîne de deux microservices : `order-api` en Python, qui appelle `pricing-engine` en Go. »
- « La contrainte : **aucun SDK d'observabilité dans le code**. Toutes les métriques viennent du noyau Linux grâce à eBPF, avec Grafana Beyla. »
- Montrer la Figure 1 :
  - Beyla tourne en **DaemonSet** sur chaque nœud, avec les droits BPF, SYS_PTRACE et NET_ADMIN.
  - Pour le service **Go** : des **uprobes** sur les fonctions de `net/http`.
  - Pour le service **Python** : des **kprobes** sur les appels système des sockets TCP. Beyla reconnaît le HTTP dans les octets.
  - Point clé : pour A, Beyla voit **deux flux**, les requêtes qu'A reçoit (serveur) et celles qu'A envoie à B (client).

### 2. Alaeddine : mise en œuvre et fiabilité (1 min)

- Stack : cluster `kind`, namespace `perf-lab`, Prometheus + Grafana, Beyla 3.43, k6.
- « Nous lançons **k6 à l'intérieur du cluster**, pour qu'un port-forward ne fausse pas les latences. »
- Vérification : 20 commandes envoyées → exactement **20 / 20 / 20** dans `/metrics` (serveur A, serveur B, client A→B).
- Difficulté réelle : dans Beyla 3.x, les filtres de découverte sont des **motifs glob, pas des regex**. Notre première config n'instrumentait rien.
- Montrer le tableau page 2 : **Beyla et k6 concordent à moins d'1 ms** (19,8 ms contre 20,2 ms en nominal). « La mesure noyau est donc fiable. »

### 3. Rami : décomposition, erreurs, tail latency (1 min 15)

- Formule : **T_interne(A) = T_serveur(A) − T_client(A→B)**.
  - En nominal, une commande de 19,8 ms = **16,6 ms dans B** + **0,4 ms de réseau** + **2,8 ms dans A**. « Si on veut accélérer, c'est B qu'il faut optimiser. »
- Erreurs (Figure 2) : 10 % de 500 injectées dans B donnent **10,25 % côté B, 10,25 % côté client A, 10,24 % côté A**.
  - « Les erreurs client d'A égalent ses erreurs serveur : A **propage** seulement. B n'a aucun appel sortant : **B est la source**. »
- Tail latency (Figure 3) : 5 % des requêtes à 600 ms.
  - **p50 = 20 ms, p99 = 605 ms, moyenne = 48 ms.**
  - « Un percentile est un rang. Le p50 tombe dans les 95 % de requêtes rapides, le p99 dans les 5 % lentes. »
  - « La moyenne décrit un utilisateur à 48 ms **qui n'existe pas** : 19 sur 20 attendent 20 ms, 1 sur 20 attend 30 fois plus. »

### 4. Adem : saturation CPU et loi de Little (1 min 15)

- B est limité à **100m de CPU**, puis k6 monte par paliers de 25 à 150 RPS (Figure 4).
- Le coude :
  - jusqu'à **50 RPS**, tout est plat (20 ms) ;
  - à **75 RPS**, B est bridé 99 % du temps et le p99 passe à 417 ms ;
  - à **100 RPS**, le débit plafonne (~100 RPS) et la latence est multipliée par 40 ;
  - à **125-150 RPS**, le débit **redescend** à 62-68 RPS et la latence atteint 22 s.
- Loi de Little, **L = λ × W** : au-delà de la capacité, la file grossit sans limite.
  - « Nous avons 1 500 utilisateurs virtuels k6 au maximum, et 68 req/s traitées. Little prédit 1 500 / 68 = **22 s**. Nous mesurons **21,8 s**. »
- La surprise, révélée par eBPF : au-delà de 100 RPS, le temps passe **dans A** (T_interne = 21 s), pas dans B. A, en Python mono-processus, sature un cœur entier. « Le goulot s'est déplacé : c'est un effondrement par congestion. »

### 5. Mohamed Ali : conclusion (30 s)

Trois leçons :
1. **Piloter par les percentiles**, pas par la moyenne.
2. **Lire Rate et Duration ensemble** pour trouver le point d'inflexion.
3. **Rester loin de 100 % d'utilisation** : sinon la file d'attente explose. Prévoir timeouts courts, *load shedding*, autoscaling.

« Et tout cela sans une ligne de code d'instrumentation. »

---

## Chiffres à connaître par cœur

| | Valeur |
|---|---|
| Nominal (50 RPS) | moyenne 20 ms, p99 24 ms, 0 % d'erreurs |
| Décomposition nominale | 16,6 ms dans B · 0,4 ms réseau · 2,8 ms dans A |
| Erreurs injectées | 10 % dans B → 10,2 % vus par l'utilisateur |
| Tail latency | p50 20 ms · p95 26 ms · p99 605 ms · moyenne 48 ms |
| Saturation | coude entre 75 et 100 RPS · plafond ≈ 100 RPS · chute à 62-68 RPS |
| Little | 1 500 en vol / 68 req/s = 22 s prédit, 21,8 s mesuré |

---

## Questions probables et réponses courtes

**Pourquoi eBPF plutôt qu'un SDK OpenTelemetry ?**
Aucun changement de code ni redéploiement, et le même outil couvre Python, Go ou un binaire fermé. En contrepartie, on a surtout des métriques et moins de détail métier qu'avec une instrumentation manuelle.

**Quel est le coût d'eBPF ?**
Les programmes sont petits et vérifiés par le noyau ; ils s'exécutent à chaque appel réseau. Le surcoût est faible : nos latences Beyla et k6 concordent à moins d'1 ms.

**Pourquoi des kprobes pour Python et des uprobes pour Go ?**
Un binaire Go embarque `net/http` avec ses symboles, donc on peut s'accrocher aux fonctions. Python passe par l'interpréteur : on observe plutôt les appels système des sockets.

**Pourquoi utiliser les moyennes pour la décomposition et pas le p99 ?**
Les moyennes s'additionnent. Les percentiles non : le p99 d'A et le p99 de son appel à B ne portent pas sur les mêmes requêtes.

**Pourquoi Beyla donne p99 = 620 ms et k6 605 ms ?**
Prometheus estime le percentile par interpolation dans un bucket d'histogramme, ici [600 ; 625 ms]. L'erreur est bornée par la largeur du bucket.

**Pourquoi le p95 oscille-t-il entre 26 et 600 ms ?**
Exactement 5 % des requêtes sont lentes, donc le p95 est pile à la frontière entre les deux populations.

**Pourquoi le débit a-t-il baissé au lieu de rester au plafond ?**
Sans *backpressure*, des centaines de requêtes s'accumulent. A, en Python mono-processus, sature un cœur juste pour les gérer. Il faut rejeter vite (503) plutôt qu'accepter tout.

**Pourquoi le serveur affiche 0 % d'erreurs alors que k6 en voit 15,8 % ?**
Ce sont des délais dépassés côté client (30 s), pas des réponses 5xx. Le pilier Errors doit aussi compter les timeouts.

---

## Démo live (optionnelle, 30 s, à préparer avant)

```bash
kubectl -n monitoring port-forward svc/kps-grafana 13000:80
# Ouvrir http://localhost:13000/d/perf-lab-red  (admin / perf-lab)
scripts/set-scenario.sh errors && scripts/run-scenario.sh demo constant 50
```

Montrer le panneau Errors : les trois courbes montent ensemble à 10 %. Si la démo échoue, revenir aux captures de l'annexe : elles montrent la même chose.

## Conseils

- Une idée par phrase, un chiffre par idée. Ne pas lire les slides.
- Montrer du doigt la courbe dont on parle.
- Répéter une fois au chronomètre : 5 minutes passent vite, la partie saturation déborde souvent.
