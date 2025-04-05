# backend/infrastructure/plugins/snapclient/discovery.py
"""
Découverte minimaliste des serveurs Snapcast via Avahi.
"""
import asyncio
import logging
import socket
from typing import List, Optional, Set

from backend.infrastructure.plugins.snapclient.models import SnapclientServer

class SnapclientDiscovery:
    """
    Détecte les serveurs Snapcast sur le réseau local via avahi-browse.
    """
    def __init__(self, timeout: float = 3.0):
        """
        Initialise le découvreur de serveurs.

        Args:
            timeout: Délai maximum (en secondes) pour la commande avahi-browse.
        """
        self.logger = logging.getLogger("plugin.snapclient.discovery")
        self._avahi_cmd = self._find_avahi_browse()
        self._timeout = timeout
        self._own_hostname = self._get_own_hostname() # Récupérer une seule fois

    def _find_avahi_browse(self) -> Optional[str]:
        """Trouve le chemin de l'exécutable avahi-browse."""
        # Utilise shutil.which qui est plus standard que 'which'
        import shutil
        path = shutil.which("avahi-browse")
        if path:
            self.logger.info(f"Utilisation de avahi-browse trouvé à: {path}")
            return path
        else:
            self.logger.warning("Impossible de trouver 'avahi-browse'. La découverte de serveurs Snapcast sera désactivée.")
            return None

    def _get_own_hostname(self) -> str:
        """Récupère le nom d'hôte local pour l'ignorer lors de la découverte."""
        try:
            # Utilise socket.gethostname() qui est standard Python
            hostname = socket.gethostname().split('.')[0].lower() # Nom court et en minuscule
            self.logger.debug(f"Nom d'hôte local détecté: {hostname}")
            return hostname
        except Exception as e:
            self.logger.warning(f"Impossible de déterminer le nom d'hôte local: {e}. Utilisation de 'oakos' par défaut.")
            return "oakos" # Nom par défaut si la détection échoue

    async def discover(self) -> List[SnapclientServer]:
        """
        Lance la découverte des serveurs Snapcast et retourne une liste de serveurs trouvés.

        Returns:
            Une liste d'objets SnapclientServer trouvés (peut être vide).
        """
        if not self._avahi_cmd:
            return []

        self.logger.info("Lancement de la découverte des serveurs Snapcast via Avahi...")
        cmd = [self._avahi_cmd, "-r", "-t", "_snapcast._tcp", "-p"] # -p pour parser, -t pour terminer
        
        servers: Set[SnapclientServer] = set() # Utiliser un set pour éviter les doublons par host

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                # Attendre la fin du processus avec timeout
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout ({self._timeout}s) lors de l'exécution de avahi-browse. Le processus sera terminé.")
                try:
                    process.kill()
                    await process.wait() # Attendre que le kill soit effectif
                except ProcessLookupError:
                    pass # Le processus était peut-être déjà mort
                except Exception as kill_e:
                    self.logger.error(f"Erreur lors du kill du processus avahi-browse: {kill_e}")
                return list(servers) # Retourner ce qu'on a pu trouver avant le timeout

            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""

            if process.returncode != 0:
                self.logger.warning(f"avahi-browse a terminé avec une erreur (code: {process.returncode}): {stderr_str.strip()}")
                # On peut quand même essayer de parser stdout s'il y a quelque chose
                if not stdout_str:
                     return []

            if not stdout_str.strip():
                 self.logger.info("Aucune sortie de avahi-browse. Aucun serveur trouvé.")
                 return []

            # Parser la sortie
            servers.update(self._parse_avahi_output(stdout_str))

        except FileNotFoundError:
            self.logger.error(f"La commande '{self._avahi_cmd}' n'a pas pu être exécutée. Avahi est-il installé?")
            self._avahi_cmd = None # Marquer comme indisponible pour les futurs appels
            return []
        except Exception as e:
            self.logger.error(f"Erreur inattendue lors de la découverte Avahi: {e}", exc_info=True)
            return []

        self.logger.info(f"Découverte terminée. {len(servers)} serveur(s) Snapcast unique(s) trouvé(s).")
        return sorted(list(servers), key=lambda s: s.name) # Trier par nom pour la cohérence

    def _parse_avahi_output(self, output: str) -> Set[SnapclientServer]:
        """
        Parse la sortie de 'avahi-browse -p -r -t _snapcast._tcp'.
        Format attendu : =;interface;protocol;service name;type;domain;... resolve ...;hostname;address;port;txt...
        """
        servers: Set[SnapclientServer] = set()
        lines = output.strip().splitlines()

        for line in lines:
            # On ne traite que les lignes commençant par '=', indiquant un service résolu
            if not line.startswith('='):
                continue

            parts = line.split(';')
            # Indices attendus (peuvent varier légèrement, être robustes)
            # 0: =
            # 2: Protocol (IPv4 or IPv6)
            # 3: Service Name (peut contenir des espaces ou caractères spéciaux)
            # 6: Status (toujours 'resolve' ?)
            # 7: Hostname (ex: 'mymac.local.')
            # 8: Address (ex: '192.168.1.10')
            # 9: Port (ex: '1704')

            if len(parts) < 10:
                self.logger.warning(f"Ligne Avahi ignorée (pas assez de parties): {line}")
                continue

            protocol = parts[2]
            hostname = parts[7].strip()
            address = parts[8].strip()
            port_str = parts[9].strip()

            # Ignorer IPv6 pour l'instant (plus simple)
            if protocol != 'IPv4':
                continue

            # Ignorer localhost
            if address.startswith('127.'):
                continue

            # Ignorer notre propre machine (comparaison insensible à la casse et sans le domaine)
            server_hostname_short = hostname.split('.')[0].lower()
            if server_hostname_short == self._own_hostname:
                # self.logger.debug(f"Ignoré serveur local: {hostname} ({address})")
                continue

            # Essayer de convertir le port
            try:
                port = int(port_str)
            except ValueError:
                self.logger.warning(f"Port invalide '{port_str}' pour le serveur {hostname}. Ligne ignorée: {line}")
                continue

            # Utiliser le nom court de l'hôte comme nom de serveur par défaut
            server_name = server_hostname_short

            # Créer et ajouter le serveur (le set gère les doublons par host)
            server = SnapclientServer(host=address, name=server_name, port=port)
            if server not in servers:
                self.logger.debug(f"Serveur Snapcast découvert: {server_name} ({address}:{port})")
                servers.add(server)

        return servers