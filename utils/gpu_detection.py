"""Module pour détecter et gérer les ressources GPU."""
import importlib
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Drapeaux pour la disponibilité
PYOPENCL_AVAILABLE = False
PYCUDA_AVAILABLE = False
NUMBA_AVAILABLE = False
GPU_AVAILABLE = False
GPU_INFO = {}

def detect_gpu():
    """Détecte les GPU disponibles et configure les bibliothèques appropriées."""
    global PYOPENCL_AVAILABLE, PYCUDA_AVAILABLE, NUMBA_AVAILABLE, GPU_AVAILABLE, GPU_INFO
    
    # Vérifier PyOpenCL (fonctionne avec NVIDIA et AMD)
    try:
        import pyopencl as cl
        PYOPENCL_AVAILABLE = True
        
        # Obtenir les plateformes et périphériques
        platforms = cl.get_platforms()
        if platforms:
            for platform in platforms:
                try:
                    devices = platform.get_devices(device_type=cl.device_type.GPU)
                    if devices:
                        GPU_AVAILABLE = True
                        for device in devices:
                            GPU_INFO[device.name] = {
                                'platform': platform.name,
                                'type': 'OpenCL',
                                'memory': device.global_mem_size,
                                'compute_units': device.max_compute_units
                            }
                        logger.info(f"GPU détecté avec PyOpenCL: {GPU_INFO}")
                except:
                    pass  # Ignorer les erreurs de périphériques spécifiques
    except ImportError:
        logger.info("PyOpenCL non disponible")
    
    # Vérifier PyCUDA (uniquement NVIDIA)
    if not GPU_AVAILABLE:
        try:
            import pycuda.driver as cuda
            import pycuda.autoinit
            PYCUDA_AVAILABLE = True
            
            # Obtenir les informations sur le périphérique
            device = cuda.Device(0)
            GPU_AVAILABLE = True
            GPU_INFO[device.name()] = {
                'platform': 'CUDA',
                'type': 'CUDA',
                'memory': device.total_memory(),
                'compute_capability': f"{device.compute_capability()[0]}.{device.compute_capability()[1]}"
            }
            logger.info(f"GPU détecté avec PyCUDA: {GPU_INFO}")
        except ImportError:
            logger.info("PyCUDA non disponible")
        except:
            logger.info("Erreur lors de l'initialisation de CUDA")
    
    # Vérifier Numba (alternative pour l'accélération)
    try:
        import numba
        from numba import cuda as numba_cuda
        NUMBA_AVAILABLE = True
        
        # Vérifier si un GPU CUDA est disponible via Numba
        if not GPU_AVAILABLE and numba_cuda.is_available():
            GPU_AVAILABLE = True
            device = numba_cuda.get_current_device()
            GPU_INFO['Numba CUDA'] = {
                'platform': 'CUDA via Numba',
                'type': 'Numba CUDA',
                'id': device.id
            }
            logger.info(f"GPU détecté avec Numba: {GPU_INFO}")
    except ImportError:
        logger.info("Numba non disponible")
    
    return GPU_AVAILABLE

def get_optimal_library():
    """Retourne la meilleure bibliothèque GPU disponible."""
    if PYOPENCL_AVAILABLE:
        return 'pyopencl'
    elif PYCUDA_AVAILABLE:
        return 'pycuda'
    elif NUMBA_AVAILABLE:
        return 'numba'
    else:
        return None

# Détecter automatiquement le GPU au démarrage
if __name__ != '__main__':
    detect_gpu()
    if GPU_AVAILABLE:
        print(f"GPU détecté et disponible: {list(GPU_INFO.keys())}")
    else:
        print("Aucun GPU compatible détecté, utilisation du CPU uniquement")
