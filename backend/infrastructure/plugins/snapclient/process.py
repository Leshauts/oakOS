# backend/infrastructure/plugins/snapclient/process.py
"""
Gestion minimaliste du processus snapclient.
"""
import asyncio
import logging
import os
import signal
from typing import Optional, List

class SnapclientProcessManager:
    """
    Gère le cycle de vie du processus snapclient OS.
    """
    def __init__(self, executable_path: str = "/usr/bin/snapclient", alsa_device: str = "default"):
        """
        Initialise le gestionnaire de processus.

        Args:
            executable_path: Chemin vers l'exécutable snapclient.
            alsa_device: Nom du périphérique ALSA à utiliser (ex: 'default', 'plughw:1,0').
        """
        self.executable_path = executable_path
        self.alsa_device = alsa_device
        self._process: Optional[asyncio.subprocess.Process] = None
        self._current_host: Optional[str] = None
        self.logger = logging.getLogger("plugin.snapclient.process")

    async def check_executable(self) -> bool:
        """Vérifie si l'exécutable existe et est exécutable."""
        if not os.path.isfile(self.executable_path):
            self.logger.error(f"L'exécutable snapclient '{self.executable_path}' n'existe pas.")
            return False
        if not os.access(self.executable_path, os.X_OK):
            self.logger.error(f"L'exécutable snapclient '{self.executable_path}' n'est pas exécutable.")
            return False
        return True

    async def start(self, host: str) -> bool:
        """
        Démarre le processus snapclient pour se connecter à un hôte.
        Arrête d'abord tout processus existant.

        Args:
            host: Adresse IP ou nom d'hôte du serveur Snapcast.

        Returns:
            True si le démarrage réussit, False sinon.
        """
        if not await self.check_executable():
            return False

        if self._process and self._process.returncode is None:
            self.logger.info(f"Processus snapclient existant trouvé (PID {self._process.pid}), arrêt avant de redémarrer.")
            await self.stop()

        # Construire la commande. '-s' spécifie le soundcard index ou name.
        # Utilisons le nom du périphérique ALSA pour plus de clarté.
        cmd: List[str] = [
            self.executable_path,
            "-h", host,
            "-s", self.alsa_device,
            # "--log-level", "debug" # Décommenter pour plus de logs de snapclient
        ]

        try:
            self.logger.info(f"Démarrage de snapclient: {' '.join(cmd)}")
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Petite attente pour voir si le processus échoue immédiatement
            await asyncio.sleep(0.5)

            if self._process.returncode is not None:
                stderr = await self._read_stream(self._process.stderr)
                self.logger.error(f"Échec du démarrage de snapclient (code: {self._process.returncode}). Erreur: {stderr}")
                self._process = None
                return False

            self._current_host = host
            self.logger.info(f"Processus snapclient démarré (PID: {self._process.pid}) pour l'hôte {host}")
            # Lancer une tâche pour surveiller la sortie standard/erreur (pour le debug)
            asyncio.create_task(self._log_output(self._process))
            return True

        except FileNotFoundError:
            self.logger.error(f"Erreur: Exécutable snapclient non trouvé à '{self.executable_path}'")
            self._process = None
            return False
        except Exception as e:
            self.logger.error(f"Erreur inattendue lors du démarrage de snapclient: {e}")
            self._process = None
            return False

    async def stop(self) -> bool:
        """
        Arrête le processus snapclient actuel (s'il existe) et nettoie.
        Tente un arrêt propre (SIGTERM) puis force (SIGKILL).
        Utilise killall en dernier recours pour nettoyer.

        Returns:
            True si l'arrêt a réussi ou s'il n'y avait rien à arrêter.
        """
        if self._process is None or self._process.returncode is not None:
            # self.logger.debug("Aucun processus snapclient actif à arrêter.")
            # Assurons le nettoyage même s'il n'y a pas de processus connu
            await self._ensure_no_snapclient_running()
            self._process = None
            self._current_host = None
            return True

        pid = self._process.pid
        self.logger.info(f"Arrêt du processus snapclient (PID: {pid}) pour l'hôte {self._current_host}...")

        try:
            # 1. Envoyer SIGTERM pour un arrêt propre
            self.logger.debug(f"Envoi de SIGTERM au PID {pid}")
            self._process.terminate()
            try:
                # Attendre un peu que le processus se termine
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
                self.logger.info(f"Processus snapclient (PID: {pid}) arrêté proprement (SIGTERM).")
            except asyncio.TimeoutError:
                # 2. Si toujours actif, envoyer SIGKILL
                self.logger.warning(f"Processus snapclient (PID: {pid}) ne répond pas à SIGTERM, envoi de SIGKILL.")
                self._process.kill()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=1.0)
                    self.logger.info(f"Processus snapclient (PID: {pid}) arrêté de force (SIGKILL).")
                except asyncio.TimeoutError:
                    self.logger.error(f"Échec de l'arrêt forcé du processus snapclient (PID: {pid}).")
            except ProcessLookupError:
                self.logger.info(f"Processus snapclient (PID: {pid}) déjà arrêté.")
            except Exception as e: # Capturer d'autres erreurs potentielles de wait()
                 self.logger.error(f"Erreur inattendue pendant l'attente de l'arrêt du processus {pid}: {e}")


        except ProcessLookupError:
            self.logger.info(f"Le processus snapclient (PID: {pid}) n'existait déjà plus.")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt du processus snapclient (PID: {pid}): {e}")
        finally:
            self._process = None
            self._current_host = None
            # 3. Mesure de sécurité : s'assurer qu'aucun processus snapclient ne traîne
            await self._ensure_no_snapclient_running()

        return True

    async def is_running(self) -> bool:
        """
        Vérifie si le processus snapclient géré est actuellement en cours d'exécution.
        Combine la vérification de l'objet Process et une vérification système (ps).

        Returns:
            True si le processus est en cours d'exécution, False sinon.
        """
        if self._process is None or self._process.returncode is not None:
            return False

        # Vérification rapide via l'objet process
        if self._process.returncode is not None:
             return False

        # Vérification système plus fiable
        try:
            proc = await asyncio.create_subprocess_exec(
                "ps", "-p", str(self._process.pid), "-o", "pid=",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL # Ignorer les erreurs si le PID n'existe pas
            )
            stdout, _ = await proc.communicate()
            is_really_running = bool(stdout.strip())
            if not is_really_running:
                self.logger.warning(f"Le processus snapclient (PID: {self._process.pid}) n'est plus trouvé par 'ps', mais l'objet process existe encore.")
                # Nettoyer notre référence interne si ps confirme qu'il est mort
                await self.stop() # Appeler stop pour un nettoyage complet
                return False
            return True
        except Exception as e:
            self.logger.warning(f"Erreur lors de la vérification du processus avec 'ps': {e}")
            # En cas d'erreur de vérification, on suppose qu'il est peut-être encore là
            # mais on logue l'incertitude. La boucle de monitoring du plugin le rattrapera si besoin.
            return self._process.returncode is None # Fallback sur l'état de l'objet process

    def get_pid(self) -> Optional[int]:
        """Retourne le PID du processus s'il est en cours d'exécution."""
        if self._process and self._process.returncode is None:
            return self._process.pid
        return None

    async def _ensure_no_snapclient_running(self):
        """Utilise killall pour s'assurer qu'aucun processus snapclient ne reste."""
        self.logger.debug("Exécution de 'killall -q snapclient' pour nettoyage final.")
        try:
            # Utiliser -q pour quiet (pas de sortie si aucun processus n'est tué)
            # Utiliser -TERM d'abord, puis -KILL si nécessaire (ici on simplifie avec -KILL directement pour garantir)
            kill_proc = await asyncio.create_subprocess_exec(
                "killall", "-KILL", "snapclient",
                stdout=asyncio.subprocess.DEVNULL, # Ignorer stdout
                stderr=asyncio.subprocess.PIPE  # Capturer stderr pour voir les erreurs (ex: command not found)
            )
            _, stderr = await kill_proc.communicate()
            if kill_proc.returncode != 0 and "no process found" not in stderr.decode().lower():
                 self.logger.warning(f"killall snapclient a échoué (code: {kill_proc.returncode}): {stderr.decode().strip()}")
            # Vérifier si des processus persistent (optionnel, killall est généralement suffisant)
            # check_proc = await asyncio.create_subprocess_exec("pgrep", "snapclient", ...)

        except FileNotFoundError:
             self.logger.warning("La commande 'killall' n'a pas été trouvée. Impossible de garantir le nettoyage des processus snapclient.")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution de killall: {e}")

    async def _read_stream(self, stream: Optional[asyncio.StreamReader]) -> str:
        """Lit le contenu d'un stream (stdout/stderr) de manière non bloquante."""
        if not stream:
            return ""
        try:
            # Lire jusqu'à 4096 bytes, sans attendre indéfiniment
            data = await asyncio.wait_for(stream.read(4096), timeout=0.1)
            return data.decode().strip()
        except asyncio.TimeoutError:
            return "" # Pas de sortie dans le délai imparti
        except Exception as e:
            self.logger.warning(f"Erreur de lecture du stream: {e}")
            return ""

    async def _log_output(self, process: asyncio.subprocess.Process):
        """Tâche de fond pour lire et logger stdout/stderr du processus."""
        try:
            while process.returncode is None:
                lines = []
                stdout_line = await self._read_stream(process.stdout)
                stderr_line = await self._read_stream(process.stderr)
                if stdout_line: lines.append(f"stdout: {stdout_line}")
                if stderr_line: lines.append(f"stderr: {stderr_line}")

                if lines:
                     self.logger.debug(f"snapclient[{process.pid}]: {' | '.join(lines)}")

                # Attendre un peu pour ne pas surcharger
                await asyncio.sleep(0.2)
        except Exception as e:
            if process.returncode is None: # Ne pas logger si le processus s'est arrêté normalement
                 self.logger.warning(f"Erreur dans la surveillance des logs snapclient[{process.pid}]: {e}")
        finally:
             # Log final après arrêt du processus
             stdout_rem = await self._read_stream(process.stdout)
             stderr_rem = await self._read_stream(process.stderr)
             if stdout_rem or stderr_rem:
                  self.logger.debug(f"snapclient[{process.pid}] sortie finale - stdout: '{stdout_rem}' | stderr: '{stderr_rem}'")