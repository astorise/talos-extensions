# Essai natif GA106 du 12 novembre 2026 : echec, pilote d'origine restaure

Une nouvelle variante ciblee GA106 a ete ecrite, compilee par GitHub Actions,
installee sur les deux RTX 3060 et testee. La compilation, le chargement des
modules et la configuration des mailboxes reussissent. Les transferts natifs
retournent des donnees incorrectes. Cette tentative ne permet donc pas un acces
P2P fiable. Le pilote et la configuration d'origine ont ete restaures et verifies.

## Ce qui a ete implemente

Le code part des sources NVIDIA 595.71.05 non modifiees, commit
`51edebee79919b54f498c19a0be31982cd97646e`. Il applique un nouveau correctif de
cet essai, sans importer le patch BAR1 communautaire precedent :

- Politique limitee a exactement deux GA106 physiques de bureau dans le meme domaine PCI.
- Selection du protocole PCIe mailbox natif de NVIDIA et de l'aperture peer existante.
- Verification des ressources et adresses de mailboxes et propagation des erreurs de configuration GSP.
- Liberation des identifiants de pairs si la configuration echoue.

Il s'agit d'une nouvelle politique et d'une adaptation du traitement de
configuration dans le pilote NVIDIA. Le moteur de transfert natif et le firmware
GSP restent ceux de NVIDIA : ce n'est pas un pilote GPU integralement reecrit.
Les tables HAL, les PTE systeme, le redimensionnement BAR1 et les bibliotheques
CUDA utilisateur ne sont pas modifies.

Le correctif est dans [595.71.05-ga106-native.patch](595.71.05-ga106-native.patch).
Son SHA-256, fins de ligne LF, est
`cfde2badf11ee71720c413c7010e19f0eba8ebf86efc2a7431da8ab80d66bdf7`.

## Compilation GitHub Actions effective

| Build | Commit | Duree du job | Resultat |
| --- | --- | --- | --- |
| [Noyau complet puis modules](https://github.com/astorise/talos-extensions/actions/runs/43169831217) | `96ae712d520ccdc1689b06e46016ad4a28486b66` | 2 h 09 min 52 s | Succes |
| [Recette actuelle avec ABI preparee](https://github.com/astorise/talos-extensions/actions/runs/43186646913) | `4db49d923caa6b6c5a29538319a41757ea2bb983` | 7 min 35 s | Succes, artefact utilise sur le noeud |

Les deux jobs ont tourne sur des runners heberges par GitHub, `ubuntu-24.04`.
Le premier a reconstruit entierement Linux ; la commande de build du noyau seule
prend 6 458 secondes. La recette actuelle prepare les en-tetes depuis les sources
verrouillees et importe les CRC du noyau exact depuis `kernel-abi`, avec controle
SHA-256 et comparaison de la configuration complete. Les cinq modules NVIDIA
sont toujours compiles depuis leurs sources dans Actions.

Les metadonnees ABI proviennent du build complet local deja prepare pour Talos.
Les tables de versions des symboles des cinq modules produits avec cette recette
ont ete comparees a celles du build complet GitHub : elles sont identiques
(258, 95, 4, 321 et 386 entrees selon le module). L'archive et les modules ont
ensuite ete verifies avant import dans le registre local, sans recompilation.

Cible testee : Talos v1.13.4, Linux 6.18.34-talos, amd64 ; NVIDIA 595.71.05 et
toolkit officiel 595.71.05-v1.19.1. Machine : ASUS PRIME Z270-P BIOS 1205,
i7-7700, deux RTX 3060 de 12 Gio, noeud `talos-4rh-gm0` / `192.168.1.139`.

## Resultats sur les cartes

| Controle | Resultat |
| --- | --- |
| Extension CI chargee | `nvidia-ga106-native-p2p:595.71.05-v1.13.4-native.1` |
| BAR1 | 256 Mio par GPU, sans redimensionnement |
| IOMMU Intel | Desactive, confirme dans le journal du noyau |
| Protection de signature pendant l'essai | `module.sig_enforce=0`, modules personnalises non approuves par le noyau stock |
| Support annonce | CUDA peer access YES et nvidia-smi P2P OK dans les deux sens |
| Configuration native | Deux mappings actives ; diagnostic `bidirectional mailbox setup completed` |
| Controles CUDA locaux, 64 Mio par GPU | 0 erreur sur chaque carte |
| Lectures distantes, 64 Mio par sens | Zeros ; 16 777 216 mots incorrects sur 16 777 216 dans chaque sens |
| Ecritures distantes, 64 Mio par sens | Le buffer du GPU destinataire garde son motif initial ; toutes les valeurs attendues sont absentes |
| Test strict fourni | Code de sortie 3, echec d'integrite |
| Essai de 512 Mio | Non lance apres l'echec a 64 Mio |

Le test [p2p-integrity.cu](p2p-integrity.cu) execute directement les loads et stores
CUDA sur les pointeurs des allocations de l'autre GPU. Il verifie les donnees
locales avant d'activer les pairs, puis les lectures dans les deux sens avant
toute ecriture distante. Aucun transfert de remplacement par la RAM CPU n'est
utilise pour les acces testes.

Un controle independant avec l'exemple NVIDIA `simpleP2P`, issu de cuda-samples
au commit `0ec046d5e99d7214cc8e9fbac2cc1e66f3019878`, echoue aussi : valeurs finales
nulles au lieu de `4 * i`, code de sortie 1. Pour borner le test, seules les
iterations du benchmark de copie ont ete reduites de 100 a 2 ; l'initialisation
depuis le CPU, les kernels de lecture distante et la verification sont inchanges.
Le debit affiche par ce benchmark n'est pas une mesure exploitable puisque les
donnees finales sont incorrectes.

Ces resultats montrent que l'acceptation des commandes de configuration GSP et
les indicateurs de support ne suffisent pas. Ils ne localisent pas definitivement
la cause du defaut du transport natif. La topologie mesuree utilise deux ports
racine distincts, CPU et PCH ; les references sont dans le [README](README.md).
Aucune conclusion de prise en charge materielle fiable n'est retenue.

## Images conservees

Artefact CI utilise, egalement importe dans le registre local avec la meme empreinte :

- `ghcr.io/astorise/nvidia-ga106-native-p2p:595.71.05-v1.13.4-native.1-4db49d923caa6b6c5a29538319a41757ea2bb983`
- `192.168.1.139:5000/nvidia-ga106-native-p2p:595.71.05-v1.13.4-native.1-ci4db49d9`
- Digest : `sha256:531049d7634e1ed93577d7d88ef2828356d946b084f621578b7677bf1da35121`.

Installer Talos construit avec cet artefact et effectivement utilise :

- `192.168.1.139:5000/installer-ga106-native-p2p:v1.13.4-native.1-ci4db49d9`
- Digest : `sha256:8c15379e07c1753126ae5ce822abc8a16d426c742099e49bcd42634e891bc861`.
- SHA-256 du fichier tar : `fa09e12e8ba42e4ab8c3216cb2939c7dddd5b777830e0fc13ce5a71fe004abb0`.

L'imager v1.13.4 valide les extensions et regenere les dependances. Le noyau
installe reste le noyau stock Talos. Le profil UKI normal a ete inspecte et ses
arguments verifies avant l'upgrade ; il ne contient aucun argument de wipe.

## Etat final verifie

- Pilote d'origine actif : `nonfree-kmod-nvidia-production:595.71.05-v1.13.4`.
- Toolkit officiel conserve : `595.71.05-v1.19.1`.
- Configuration effective complete identique a celle sauvegardee immediatement avant l'essai.
- Arguments de demarrage d'origine, dont `module.sig_enforce=1`, sans les arguments IOMMU experimentaux.
- Noeud `talos-4rh-gm0` Ready et de nouveau ouvert a la planification, deux GPU allouables.
- Kernel CUDA et relecture de 16 Mio verifies sur chaque GPU apres restauration ; peer access NO attendu avec le pilote d'origine.
- etcd, kubelet, containerd et CRI sains ; registre, CoreDNS, controleur ARC et cinq listeners disponibles.
- Pods de test et de reservation supprimes. Le vieux noeud `host-003`, deja NotReady avant l'essai, n'a pas ete modifie.

Installer restaure :
`factory.talos.dev/installer/26124abcbd408be693df9fe852c80ef1e6cc178e34d7d7d8430a28d1130b4227:v1.13.4`,
digest `sha256:7d756d9a5658ec041d1f0bcbec04e525509156dfd263d799264722400de4a541`.

## Traces locales

- `_out/native-ci-full` et `_out/native-ci-fast` : artefacts Actions et leurs verifications.
- `_out/native-trial/ci-abi-comparison.json` et `fast-ci-abi-comparison.json` : comparaison des CRC entre builds.
- `_out/native-trial/p2p-64MiB.txt`, `test-result.json`, `simpleP2P-native.txt` : resultats des tests.
- `_out/native-trial/dmesg-native.txt`, `memory-native.txt` : diagnostics pendant l'essai.
- `_out/native-trial/installer-verification.json` : controle des profils UKI.
- `_out/native-trial/cuda-after-rollback.txt`, `rollback-verification.json`, `result.json` : restauration verifiee.

Les sauvegardes completes de configuration et d'etcd sont egalement dans
`_out/native-trial`, ignore par Git. Elles contiennent des secrets et restent
locales ; elles ne sont pas publiees dans le fork.
