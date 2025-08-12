import re
from typing import List, Optional


class CodeExtractor:
    @staticmethod
    def extract_pip_packages(response: str) -> List[str]:
        # Extract all pip install lines from bash code blocks
        bash_block_pattern = r'```(?:bash|sh|shell)?\s*\n(.*?)\n```'
        bash_blocks = re.findall(bash_block_pattern, response, re.IGNORECASE | re.DOTALL)
        
        packages = []
        for block in bash_blocks:
            # Find all lines containing pip install
            pip_lines = [line.strip() for line in block.split('\n') if 'pip install' in line]
            
            for line in pip_lines:
                # Skip pip upgrade commands
                if '--upgrade pip' in line or 'pip install --upgrade pip' in line:
                    continue
                
                # Extract packages from pip install command
                pip_match = re.search(r'pip install\s+(.+?)(?:\s*$|&&|;)', line)
                if pip_match:
                    package_text = pip_match.group(1).strip()
                    # Filter out flags and keep only package names
                    package_list = [pkg.strip() for pkg in package_text.split() 
                                  if pkg.strip() and not pkg.startswith('-') and pkg != 'pip']
                    packages.extend(package_list)
        
        return packages
    
    @staticmethod
    def extract_apt_packages(response: str) -> List[str]:
        # Match bash code blocks containing apt-get install commands
        bash_block_pattern = r'```(?:bash|sh|shell)?\s*\n(.*?)\n```'
        bash_blocks = re.findall(bash_block_pattern, response, re.IGNORECASE | re.DOTALL)
        
        packages = []
        for block in bash_blocks:
            # Look for apt-get install commands within each bash block
            apt_lines = [line.strip() for line in block.split('\n') if 'apt-get' in line and 'install' in line]
            
            for line in apt_lines:
                # Extract packages from apt-get install command
                apt_match = re.search(r'apt-get.*?install.*?-y\s+(.*?)(?:\s*$|&&|;)', line)
                if apt_match:
                    package_text = apt_match.group(1).strip()
                    # Filter out common flags and keep only package names
                    package_list = [pkg.strip() for pkg in package_text.split() if pkg.strip() and not pkg.startswith('-')]
                    packages.extend(package_list)
        
        return packages
    
    @staticmethod
    def extract_python_script(response: str) -> Optional[str]:
        python_pattern = r'```python\s*\n(.*?)\n```'
        matches = re.findall(python_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        return None