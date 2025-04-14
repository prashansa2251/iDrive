document.addEventListener('DOMContentLoaded', function () {
    const cardViewBtn = document.getElementById('cardViewBtn');
    const tableViewBtn = document.getElementById('tableViewBtn');
    const cardView = document.getElementById('cardView');
    const tableView = document.getElementById('tableView');
    const noFiles = document.getElementById('noFiles');
    const withFiles = document.getElementById('withFiles');
    const searchInput = document.getElementById('searchInput');
    const rootFolderPath = document.getElementById('folderPath').value;
    const selectAllCheckBox = document.getElementById('selectAllCheckBox');
    const newFolderBtn = document.getElementById('newFolderBtn');
    const newFolder = document.getElementById('newFolder');
    const currentPathFolder = document.getElementById('currentPath');
    const noFilesFolder = document.getElementById('noFilesFolder');
    const renameSection = document.getElementById('renameSection');
    let currentPath = ''; // Tracks the current directory path
    let allItems = []; // Store all items from current directory for filtering
    let lastCheckedIndex = -1;
    let selectedItems = [];
    let isShiftPressed = false;

    newFolderBtn.addEventListener('click', function () {
        toggleSpinner();
        noFiles.classList.add('d-none');
        withFiles.classList.add('d-none');
        newFolder.classList.remove('d-none');
        currentPathFolder.value = currentPath;
        toggleSpinner();
    });

    // Toggle Views
    cardViewBtn.addEventListener('click', function () {
        syncSelectionState();
        cardView.style.display = 'flex';
        tableView.style.display = 'none';
        cardViewBtn.innerHTML = '<i class="fa-solid fa-table-cells-large "></i><i class="fa-solid fa-check ms-1 fa-sm"></i>'
        tableViewBtn.innerHTML = '<i class="fa-solid fa-list-ul  text-muted"></i>'
        cardViewBtn.classList.add('text-primary');
        tableViewBtn.classList.remove('text-primary');
    });

    tableViewBtn.addEventListener('click', function () {
        syncSelectionState();
        cardView.style.display = 'none';
        tableView.style.display = 'block';
        tableViewBtn.innerHTML = '<i class="fa-solid fa-list-ul "></i><i class="fa-solid fa-check ms-1 fa-sm"></i>'
        cardViewBtn.innerHTML = '<i class="fa-solid fa-table-cells-large  text-muted"></i>'
        tableViewBtn.classList.add('text-primary');
        cardViewBtn.classList.remove('text-primary');

    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Shift') {
            isShiftPressed = true;
        } else if (e.key === 'Control' || e.key === 'Meta') {
            // For Windows/Linux Ctrl key or Mac Command key
            isCtrlPressed = true;
        }
    });

    document.addEventListener('keyup', function (e) {
        if (e.key === 'Shift') {
            isShiftPressed = false;
        } else if (e.key === 'Control' || e.key === 'Meta') {
            isCtrlPressed = false;
        }
    });
    window.showRenameForm = function (item) {
        const renameNameInput = document.getElementById('renameName');
        const renamePathInput = document.getElementById('renamePath');
        const isDirectoryInput = document.getElementById('isDirectory');
        const originalNameInput = document.getElementById('originalName');
        const oldNameInput = document.getElementById('oldName');
        const extensionInput = document.getElementById('fileExtension');

        // Assign basic values
        renamePathInput.value = item.path;
        isDirectoryInput.value = item.is_directory;
        originalNameInput.value = item.original_filename;
        oldNameInput.value = item.name;

        if (!item.is_directory) {
            const nameParts = item.name.split('.');
            if (nameParts.length > 1) {
                const ext = nameParts.pop(); // Remove and get extension
                extensionInput.value = '.' + ext;
                renameNameInput.value = nameParts.join('.');
            } else {
                extensionInput.value = '';
                renameNameInput.value = item.name;
            }
        } else {
            extensionInput.value = ''; // folders don’t have extensions
            renameNameInput.value = item.name;
        }

        // Show section
        withFiles.classList.add('d-none');
        renameSection.classList.remove('d-none');
        renameSection.scrollIntoView({ behavior: 'smooth' });
    }

    // Search functionality
    searchInput.addEventListener('input', function () {
        const searchTerm = this.value.toLowerCase().trim();
        filterItems(searchTerm);
    });
    function fetchStorageStatus() {
        fetch('/storage_status', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                const storageContainer = document.getElementById('storageStatus');
                if (!storageContainer) return;

                const { used, allocated, danger, percentage } = data;

                // Determine danger class for text and progress bar
                const dangerClass = danger ? 'text-danger' : 'text-muted';
                const progressBarClass = danger ? 'bg-danger' : 'bg-info';

                // Update the HTML inside #storageStatus
                storageContainer.innerHTML = `
            <div class="container p-0 m-0 ms-3 ${dangerClass}" style="width: 50%;">
                <span class="fs-8"><i class="fa-solid fa-cloud"></i> Storage (${percentage}% Full)</span>
                <div class="progress" role="progressbar" aria-valuenow="${percentage}" aria-valuemin="0" aria-valuemax="100" style="height: 5px;">
                    <div class="progress-bar ${progressBarClass}" style="width: ${percentage}%;"></div>
                </div>
                <span class="fs-9">${used} of ${allocated} used</span>
            </div>
        `;
            })
            .catch(error => {
                console.error("Error fetching storage status:", error);
            });
    }


    function filterItems(searchTerm) {
        if (!searchTerm) {
            // If search is empty, show all items
            updateCardView(allItems);
            updateTableView(allItems);
            syncSelectionState();
            return;
        }

        const filteredItems = allItems.filter(item =>
            item.name.toLowerCase().includes(searchTerm)
        );

        // Update views with filtered items
        updateCardView(filteredItems);
        updateTableView(filteredItems);
        syncSelectionState();

        // Show/hide empty state
        if (filteredItems.length === 0) {
            cardView.innerHTML = `<div class="col-12 w-100 d-grid justify-content-center align-content-center text-center py-5">
            <p class="text-muted">No files matched your search</p>
        </div>`;
            tableView.querySelector('tbody').innerHTML = `<tr>
            <td colspan="5" class="text-center py-4">No files matched your search</td>
        </tr>`;
        }
    }

    // Fetch Directories & Files
    window.fetchFileList = function (folderPath = '') {
        fetchStorageStatus();
        console.log("Fetching folder:", folderPath);
        toggleSpinner();
        fetch('/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: folderPath })
        })
            .then(response => response.json())
            .then(data => {
                console.log("API Response:", data);

                if (data.error) {
                    console.error("Error fetching files:", data.error);
                    toggleSpinner();
                    return;
                }

                currentPath = folderPath;
                updateBreadcrumb();

                // Clear search when navigating
                searchInput.value = '';

                // Store all items for search filtering
                allItems = data;

                if (data.length === 0) {
                    if (currentPath === rootFolderPath) {
                        noFiles.classList.remove('d-none');
                        withFiles.classList.add('d-none');
                        noFilesFolder.classList.add('d-none');
                    } else {
                        noFiles.classList.add('d-none');
                        withFiles.classList.add('d-none');
                        noFilesFolder.classList.remove('d-none');
                        console.log("Empty folder:", currentPath);
                    }

                } else {
                    noFiles.classList.add('d-none');
                    withFiles.classList.remove('d-none');
                    noFilesFolder.classList.add('d-none');
                    updateCardView(data);
                    updateTableView(data);
                    deselectAllRows();
                    syncSelectionState();
                }
                toggleSpinner();
            })
            .catch(error => {
                console.error("Fetch error:", error);
                toggleSpinner();
            });
    };

    // Update Breadcrumb & Back Button 
    function updateBreadcrumb() {
        const breadcrumbElements = [
            document.getElementById('breadcrumb'),
            document.getElementById('breadcrumbFolder'),
        ];

        breadcrumbElements.forEach(breadcrumb => {
            if (!breadcrumb) return;

            breadcrumb.innerHTML = '';
            const parts = currentPath.split('/').filter(p => p);
            console.log("Current path:", currentPath);

            // Always start with Home, linking to the user's base folder
            breadcrumb.innerHTML = `<li class="breadcrumb-item"><a href="javascript:void(0)" onclick="fetchFileList('${rootFolderPath}')">Home</a></li>`;

            if (parts.length === 0) return;

            let fullPath = '';

            parts.forEach((part, index) => {
                fullPath += (index === 0 ? '' : '/') + part;

                if (index === 0) {
                    const nameParts = part.split('_');
                    if (nameParts.length > 1) {
                        const displayName = nameParts.slice(1).join(' ').replace(/_/g, ' ');
                        const formattedName = formatFolderName(displayName);

                        if (parts.length > 1) {
                            const fullPathWithSlash = fullPath + '/';
                            breadcrumb.innerHTML += `<li class="breadcrumb-item"><a href="javascript:void(0)" onclick="fetchFileList('${fullPathWithSlash}')">${formattedName}</a></li>`;
                        } else {
                            breadcrumb.innerHTML += `<li class="breadcrumb-item active">${formattedName}</li>`;
                        }
                    } else {
                        breadcrumb.innerHTML += `<li class="breadcrumb-item${parts.length === 1 ? ' active' : ''}">
                    ${parts.length > 1 ? `<a href="javascript:void(0)" onclick="fetchFileList('${fullPath}/')">${part}</a>` : part}
                </li>`;
                    }
                } else {
                    const fullPathWithSlash = fullPath + '/';
                    const isLastItem = index === parts.length - 1;
                    const displayName = formatFolderName(part);

                    if (isLastItem) {
                        breadcrumb.innerHTML += `<li class="breadcrumb-item active">${displayName}</li>`;
                    } else {
                        breadcrumb.innerHTML += `<li class="breadcrumb-item"><a href="javascript:void(0)" onclick="fetchFileList('${fullPathWithSlash}')">${displayName}</a></li>`;
                    }
                }
            });
        });
    }


    function updateCardView(items) {
        const cardViewContainer = document.getElementById("cardView");
        cardViewContainer.innerHTML = ""; // Clear existing cards

        items.forEach(item => {
            // Create card element
            const col = document.createElement('div');
            const card = document.createElement('div');
            // Set card attributes and classes
            col.className = 'col';
            card.className = 'card h-100';
            card.dataset.path = item.path;
            card.dataset.originalfilename = item.original_filename;
            card.dataset.name = item.name;
            card.dataset.isDirectory = item.is_directory;
            card.dataset.sizebytes = item.sizebytes;

            // Only make files selectable (not directories)
            if (!item.is_directory) {
                card.className += ' card-selectable';
                card.onclick = function (event) { handleItemSelection(event, this); };
            } else {
                card.className += ' card-clickable';
                card.onclick = function (event) {
                    const target = event.target;

                    // Prevent folder navigation if the click was on the dropdown button or menu
                    if (
                        target.closest('.folderDropdown') ||
                        target.closest('.dropdown-menu')
                    ) {
                        return;
                    }

                    if (item.is_directory) {
                        fetchFileList(item.path);
                    }
                };

            }

            // Card HTML content
            card.innerHTML = `
        <div class="card-body p-2">
            ${item.is_directory ? `
            <div class='d-flex justify-content-end'>
                    <button class="btn btn-sm btn-outline-light fs-8 no-loader folderDropdown" id="folderDropdownCard_${item.name}" 
                    data-bs-toggle="dropdown" aria-expanded="false" style="border:none;"><i class="fa-solid fa-ellipsis-vertical text-muted"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end p-3 shadow" aria-labelledby="folderDropdownCard_${item.name}" style="border-radius: 12px;">
                        ${!item.user_folder ? `
                        ${item.owner ? `
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); showRenameForm(${JSON.stringify(item)})'>
                                <i class="fa-solid fa-i-cursor pe-1 me-2 ms-1"></i> Rename
                        </a>
                        `: ``}
                        `: ``}
                        
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); downloadFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-download me-2" ></i> Download
                        </a>
                        ${item.owner ? `
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); copyFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-copy me-2" ></i> Copy
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); moveFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-file-import me-2" ></i> Move
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); deleteFolder("${item.path}", "${item.name}")'>
                                <i class="fa-solid fa-trash-can me-2"></i> Delete
                        </a>
                        
                        `: ``}
                    </ul>
            </div>
            ` : `<div class='d-flex justify-content-end'>
                    <button class="btn btn-sm btn-outline-light fs-8 no-loader folderDropdown" id="fileDropdownCard_${item.name}" 
                    data-bs-toggle="dropdown" aria-expanded="false" style="border:none;"><i class="fa-solid fa-ellipsis-vertical text-muted"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end p-3 shadow" aria-labelledby="fileDropdownCard_${item.name}" style="border-radius: 12px;">
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); showRenameForm(${JSON.stringify(item)})'>
                                <i class="fa-solid fa-i-cursor pe-1 me-2 ms-1"></i> Rename
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); copyFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-copy me-2" ></i> Copy
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); moveFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-file-import me-2" ></i> Move
                        </a>
                        <a class="dropdown-item fs-7" href="/stream_download/${item.path}" onclick="event.stopPropagation(); handleDownload(event,this);">
                                <i class="fa-solid fa-download me-2 "></i> Download
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick="event.stopPropagation(); deleteFile('${item.path}','${item.name}')">
                                <i class="fa-solid fa-trash-can me-2" ></i> Delete
                        </a>
                    </ul>
            </div>
            `}
            <div class='p-3'>
            <div class="text-center mb-2">
                ${item.is_directory ? `${item.user_folder ? `<i class="fa-solid fa-user-tag text-muted fs-3"></i>` : `<i class="fa-solid fa-folder text-muted fs-3"></i>`}` : getFileIcon(item.original_filename)}
            </div>
            <div class="text-center">
                <h6 class="card-title text-truncate mb-1">${item.name}</h6>
            </div>
            <div class="text-center text-muted fs-8">
                ${item.allocated_storage ? (item.is_directory ? item.size + '/' + item.allocated_storage : item.size) : item.size}
            </div>
            <div class="text-center text-muted fs-8">
                ${item.upload_date || ''}
            </div>
        </div></div></div>
    `;

            // Create and append the hidden checkbox
            const checkbox = document.createElement('input');
            checkbox.className = 'form-check-input card-checkbox d-none';
            checkbox.type = 'checkbox';
            checkbox.value = item.path;
            if (item.is_directory) {
                checkbox.disabled = true;
            }

            // Append the checkbox to the card
            card.appendChild(checkbox);
            col.appendChild(card);
            // Append the card to the container
            cardViewContainer.appendChild(col);
        });
    }

    function updateTableView(items) {
        const tableBody = document.querySelector("#tableView tbody");
        tableBody.innerHTML = ""; // Clear existing table rows

        items.forEach(item => {
            // Create row element
            const row = document.createElement('tr');

            // Set row attributes
            row.className = item.is_directory ? 'tr-clickable' : 'tr-selectable';
            row.dataset.path = item.path;
            row.dataset.name = item.name;
            row.dataset.originalfilename = item.original_filename;
            row.dataset.isDirectory = item.is_directory;
            row.dataset.sizebytes = item.sizebytes;
            row.onclick = function (event) { handleItemSelection(event, this); };

            // Set row HTML content
            row.innerHTML = `
        <td class="p-1 align-middle text-center">${item.is_directory ? `${item.user_folder ? `<i class="fa-solid fa-user-tag text-muted fs-4"></i>` : `<i class="fa-solid fa-folder text-muted fs-4"></i>`}` : getFileIcon(item.original_filename)}</td>
        <td class='fs-7 align-middle'>${item.name}</td>
        <td class='text-muted fs-8 align-middle'>${item.size}</td>
        <td class='text-muted fs-8 align-middle'>${item.upload_date || ''}</td>
        <td>
            ${item.is_directory ? `
                <div class='d-flex'>
                    <button class="btn btn-sm btn-outline-light fs-8 no-loader folderDropdown" id="folderDropdownTable_${item.name}" 
                    data-bs-toggle="dropdown" aria-expanded="false" style="border:none;"><i class="fa-solid fa-ellipsis-vertical text-muted"></i></button>
                    <ul class="dropdown-menu dropdown-menu-end p-3 shadow" aria-labelledby="folderDropdownTable_${item.name}" style="border-radius: 12px;">
                        ${!item.user_folder ? `
                        ${item.owner ? `
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); showRenameForm(${JSON.stringify(item)})'>
                                <i class="fa-solid fa-i-cursor pe-1 me-2 ms-1"></i> Rename
                        </a>
                        `: ``}
                        `: ``}
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); downloadFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-download me-2" ></i> Download
                        </a>
                        ${item.owner ? `
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); copyFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-copy me-2" ></i> Copy
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); moveFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-file-import me-2" ></i> Move
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); deleteFolder("${item.path}", "${item.name}")'>
                                <i class="fa-solid fa-trash-can me-2"></i> Delete
                        </a>
                        `: ``}
                        
                        
                    </ul>
                </div>
            ` : `
                <div class='d-flex'>
                    <button class="btn btn-sm btn-outline-light fs-8 no-loader folderDropdown" id="fileDropdownTable_${item.name}" 
                    data-bs-toggle="dropdown" aria-expanded="false" style="border:none;"><i class="fa-solid fa-ellipsis-vertical text-muted"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end p-3 shadow" aria-labelledby="fileDropdownTable_${item.name}" style="border-radius: 12px;">
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); showRenameForm(${JSON.stringify(item)})'>
                                <i class="fa-solid fa-i-cursor pe-1 me-2 ms-1"></i> Rename
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); copyFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-copy me-2" ></i> Copy
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick='event.stopPropagation(); moveFolder(${JSON.stringify(item.path)}, ${JSON.stringify(item.name)})'>
                                <i class="fa-solid fa-file-import me-2" ></i> Move
                        </a>
                        <a class="dropdown-item fs-7" href="/stream_download/${item.path}" onclick="event.stopPropagation(); handleDownload(event,this);">
                                <i class="fa-solid fa-download me-2 "></i> Download
                        </a>
                        <a class="dropdown-item fs-7" href="javascript:void(0)" onclick="event.stopPropagation(); deleteFile('${item.path}','${item.name}')">
                                <i class="fa-solid fa-trash-can me-2" ></i> Delete
                        </a>
                    </ul>
            </div>
            `}
        </td>`;

            // Create and append the hidden checkbox
            const checkboxCell = document.createElement('input');
            checkboxCell.className = 'form-check-input row-checkbox d-none';
            checkboxCell.type = 'checkbox';
            checkboxCell.value = item.path;
            if (item.is_directory) {
                checkboxCell.disabled = true;
            }

            // Append the checkbox to the row
            row.appendChild(checkboxCell);

            // Append the row to the table
            tableBody.appendChild(row);
        });
    }


    window.handleDownload = function (event, button) {
        toggleSpinner();
        event.stopPropagation(); // Prevent parent click events

        // Wait for ~2 seconds (simulate download start)
        setTimeout(() => {
            toggleSpinner();
        }, 2000);
    }

    // Delete File Function
    window.deleteFile = function (path, name) {
        if (confirm(`Are you sure you want to delete ${name}?`)) {
            fetch(`/delete/${path}`, {
                method: 'POST'
            })
                .then(response => response.json())  // Parse JSON response
                .then(data => {
                    if (data.message) {
                        message = data.message;
                        fetchFileList(currentPath);
                        showToast(message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while deleting the file');
                });
        }
    };
    window.deleteFolder = function (folderPath, folderName) {
        if (confirm(`Are you sure you want to delete the folder "${folderName}"?`)) {
            fetch(`/delete_folder/${encodeURIComponent(folderPath)}`, {
                method: 'POST'
            })
                .then(response => response.json())
                .then(data => {
                    if (data.message) {
                        const message = data.message;
                        fetchFileList(currentPath); // Refresh the list
                        showToast(message);         // Show success toast
                    } else {
                        alert('Folder deletion failed.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while deleting the folder.');
                });
        }
    };


    // Function to determine file icons based on filename extension
    window.getFileIcon = function (filename) {
        if (!filename) return '<i class="fa-solid fa-file text-muted fs-4"></i>';

        const extension = filename.split('.').pop().toLowerCase();

        // Image files
        if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(extension)) {
            return '<i class="fa-solid fa-file-image text-muted fs-4"></i>';
        }

        // Video files
        if (['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv'].includes(extension)) {
            return '<i class="fa-solid fa-file-video text-muted fs-4"></i>';
        }

        // Audio files
        if (['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac'].includes(extension)) {
            return '<i class="fa-solid fa-file-audio text-muted fs-4"></i>';
        }

        // Document files
        if (['pdf'].includes(extension)) {
            return '<i class="fa-solid fa-file-pdf text-muted fs-4"></i>';
        }

        if (['doc', 'docx', 'rtf', 'txt', 'odt'].includes(extension)) {
            return '<i class="fa-solid fa-file-word text-muted fs-4"></i>';
        }

        if (['xls', 'xlsx', 'csv', 'ods'].includes(extension)) {
            return '<i class="fa-solid fa-file-excel text-muted fs-4"></i>';
        }

        if (['ppt', 'pptx', 'odp'].includes(extension)) {
            return '<i class="fa-solid fa-file-powerpoint text-muted fs-4"></i>';
        }

        // Archive files
        if (['zip', 'rar', '7z', 'tar', 'gz'].includes(extension)) {
            return '<i class="fa-solid fa-file-zipper text-muted fs-4"></i>';
        }

        // Code files
        if (['html', 'css', 'js', 'php', 'py', 'java', 'c', 'cpp', 'json'].includes(extension)) {
            return '<i class="fa-solid fa-file-code text-muted fs-4"></i>';
        }

        // Default file icon
        return '<i class="fa-solid fa-file text-muted fs-4"></i>';
    };

    function formatFolderName(name) {
        return name
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }
    // Unified function to handle selection in both table and card views
    window.handleItemSelection = function (event, element) {
        // Check if it's a directory - if so, navigate to it
        const target = event.target;
        if (
            target.closest('.folderDropdown') ||
            target.closest('.dropdown-menu')
        ) {
            return; // Do nothing if dropdown was clicked
        }
        if (element.dataset.isDirectory === 'true') {

            fetchFileList(element.dataset.path);
            return;
        }

        // Prevent default behavior
        event.preventDefault();

        // Determine if this is a card or table row
        const isCard = element.classList.contains('card-selectable');
        const isRow = element.classList.contains('tr-selectable');

        // Get the appropriate checkbox and visual class
        const checkboxClass = isCard ? '.card-checkbox' : '.row-checkbox';
        const activeClass = isCard ? 'border-primary' : 'table-active';

        // Get the checkbox
        const checkbox = element.querySelector(checkboxClass);
        if (!checkbox) {
            console.error('Checkbox not found for element:', element);
            return;
        }

        // Toggle checkbox state
        checkbox.checked = !checkbox.checked;

        // Toggle visual selection
        if (checkbox.checked) {
            element.classList.add(activeClass);
        } else {
            element.classList.remove(activeClass);
        }

        // Update the selectedItems array
        const itemPath = element.dataset.path;
        if (checkbox.checked) {
            if (!selectedItems.includes(itemPath)) {
                selectedItems.push(itemPath);
            }
        } else {
            const index = selectedItems.indexOf(itemPath);
            if (index > -1) {
                selectedItems.splice(index, 1);
            }
        }

        // Find corresponding element in the other view
        const selector = isCard
            ? `.tr-selectable[data-path="${itemPath}"]`
            : `.card-selectable[data-path="${itemPath}"]`;
        const correspondingElement = document.querySelector(selector);

        // Update corresponding element if it exists
        if (correspondingElement) {
            const correspondingCheckbox = correspondingElement.querySelector(
                isCard ? '.row-checkbox' : '.card-checkbox'
            );

            if (correspondingCheckbox) {
                correspondingCheckbox.checked = checkbox.checked;

                if (checkbox.checked) {
                    correspondingElement.classList.add(isCard ? 'table-active' : 'border-primary');
                } else {
                    correspondingElement.classList.remove(isCard ? 'table-active' : 'border-primary');
                }
            }
        }

        // Handle shift-click for range selection
        if (isShiftPressed && lastCheckedIndex >= 0) {
            // Get all selectable elements of the same type
            const allElements = Array.from(document.querySelectorAll(
                isCard ? '.card-selectable' : '.tr-selectable'
            ));
            const currentIndex = allElements.indexOf(element);

            if (currentIndex !== -1) {
                const start = Math.min(currentIndex, lastCheckedIndex);
                const end = Math.max(currentIndex, lastCheckedIndex);

                for (let i = start; i <= end; i++) {
                    const elementInRange = allElements[i];
                    const checkboxInRange = elementInRange.querySelector(checkboxClass);

                    if (checkboxInRange) {
                        // Apply same checked state
                        checkboxInRange.checked = checkbox.checked;

                        // Update visual state
                        if (checkbox.checked) {
                            elementInRange.classList.add(activeClass);
                            if (!selectedItems.includes(elementInRange.dataset.path)) {
                                selectedItems.push(elementInRange.dataset.path);
                            }
                        } else {
                            elementInRange.classList.remove(activeClass);
                            const idx = selectedItems.indexOf(elementInRange.dataset.path);
                            if (idx > -1) {
                                selectedItems.splice(idx, 1);
                            }
                        }

                        // Update corresponding element in other view
                        const otherViewSelector = isCard
                            ? `.tr-selectable[data-path="${elementInRange.dataset.path}"]`
                            : `.card-selectable[data-path="${elementInRange.dataset.path}"]`;
                        const otherElement = document.querySelector(otherViewSelector);

                        if (otherElement) {
                            const otherCheckbox = otherElement.querySelector(
                                isCard ? '.row-checkbox' : '.card-checkbox'
                            );

                            if (otherCheckbox) {
                                otherCheckbox.checked = checkbox.checked;

                                if (checkbox.checked) {
                                    otherElement.classList.add(isCard ? 'table-active' : 'border-primary');
                                } else {
                                    otherElement.classList.remove(isCard ? 'table-active' : 'border-primary');
                                }
                            }
                        }
                    }
                }
            }
        }

        // Update last checked index based on view type
        lastCheckedIndex = Array.from(document.querySelectorAll(
            isCard ? '.card-selectable' : '.tr-selectable'
        )).indexOf(element);

        // Update the UI
        updateSelectionUI();
    };
    window.syncSelectionState = function () {
        // Apply selection states from selectedItems array to both views
        selectedItems.forEach(itemPath => {
            // Update table view
            const tableRow = document.querySelector(`.tr-selectable[data-path="${itemPath}"]`);
            if (tableRow) {
                const tableCheckbox = tableRow.querySelector('.row-checkbox');
                if (tableCheckbox) {
                    tableCheckbox.checked = true;
                    tableRow.classList.add('table-active');
                }
            }

            // Update card view
            const card = document.querySelector(`.card-selectable[data-path="${itemPath}"]`);
            if (card) {
                const cardCheckbox = card.querySelector('.card-checkbox');
                if (cardCheckbox) {
                    cardCheckbox.checked = true;
                    card.classList.add('border-primary');
                }
            }
        });

        // Update selection UI
        updateSelectionUI();
    }

    // Modified selectAllRows function
    window.selectAllRows = function () {
        // Handle table rows
        const selectableRows = document.querySelectorAll('.tr-selectable');
        selectableRows.forEach(row => {
            const checkbox = row.querySelector('.row-checkbox');
            if (checkbox) {
                checkbox.checked = true;
                row.classList.add('table-active');

                const itemPath = row.dataset.path;
                if (!selectedItems.includes(itemPath)) {
                    selectedItems.push(itemPath);
                }
            }
        });

        // Handle cards - must be synchronized
        const selectableCards = document.querySelectorAll('.card-selectable');
        selectableCards.forEach(card => {
            const checkbox = card.querySelector('.card-checkbox');
            if (checkbox) {
                checkbox.checked = true;
                card.classList.add('border-primary');
            }
        });

        // Update UI
        updateSelectionUI();
    };

    window.deselectAllRows = function () {
        // Handle table rows
        const selectableRows = document.querySelectorAll('.tr-selectable');
        selectableRows.forEach(row => {
            const checkbox = row.querySelector('.row-checkbox');
            if (checkbox) {
                checkbox.checked = false;
                row.classList.remove('table-active');
            }
        });

        // Handle cards - must be synchronized
        const selectableCards = document.querySelectorAll('.card-selectable');
        selectableCards.forEach(card => {
            const checkbox = card.querySelector('.card-checkbox');
            if (checkbox) {
                checkbox.checked = false;
                card.classList.remove('border-primary');
            }
        });

        // Clear selectedItems array
        selectedItems = [];

        // Update UI
        updateSelectionUI();
    };

    // Update UI based on selection
    window.updateSelectionUI = function () {
        // Highlight selected rows
        document.querySelectorAll('.tr-selectable').forEach(row => {
            const checkbox = row.querySelector('.row-checkbox');
            if (checkbox.checked) {
                row.classList.add('table-active');
            } else {
                row.classList.remove('table-active');
            }
        });

        // Update bulk action buttons visibility
        const bulkActionContainer = document.getElementById('bulk-actions');
        if (selectedItems.length > 0) {
            bulkActionContainer.classList.remove('d-none');
            document.getElementById('selected-count').textContent = selectedItems.length;
        } else {
            bulkActionContainer.classList.add('d-none');
        }
    }
    // Reset progress UI to initial state
    window.resetProgressUI = function () {
        const container = document.getElementById('download-progress-container');
        const errorsContainer = document.getElementById('download-errors-container');
        const progressBar = document.getElementById('download-total-progress');
        const statusText = document.getElementById('download-status-text');
        const speedElement = document.getElementById('download-speed');
        const etaElement = document.getElementById('download-eta');

        if (container) {
            container.style.display = 'block';
        }

        if (errorsContainer) {
            errorsContainer.innerHTML = '';
            errorsContainer.classList.add('d-none');
        }

        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
        }

        if (statusText) {
            statusText.textContent = 'Preparing download...';
        }

        if (speedElement) {
            speedElement.textContent = '-';
        }

        if (etaElement) {
            etaElement.textContent = '-';
        }
    }

    window.parseSizeToBytes = function (sizeStr) {
        sizeStr = sizeStr.trim();

        // Empty string or unknown format
        if (!sizeStr || sizeStr === '-') return 0;

        const units = {
            'B': 1,
            'Bytes': 1,
            'KB': 1024,
            'MB': 1024 * 1024,
            'GB': 1024 * 1024 * 1024,
            'TB': 1024 * 1024 * 1024 * 1024
        };

        // Extract number and unit
        const matches = sizeStr.match(/^([\d.]+)\s*([A-Za-z]+)$/);
        if (!matches) return 0;

        const value = parseFloat(matches[1]);
        const unit = matches[2];

        return value * (units[unit] || 0);
    };

    window.formatTime = function (seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.round(seconds % 60);
            return `${minutes}m ${remainingSeconds}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const remainingMinutes = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${remainingMinutes}m`;
        }
    }

    // UI update functions
    window.addErrorItem = function (id, filename, errorMessage) {
        const errorsContainer = document.getElementById('download-errors-container');
        if (!errorsContainer) return;

        errorsContainer.classList.remove('d-none');

        const item = document.createElement('div');
        item.id = id;
        item.className = 'p-2 border-bottom small';

        item.innerHTML = `
    <div class="d-flex justify-content-between text-danger">
        <div class="text-truncate fs-8" title="${filename}" style="max-width: 200px;">${filename}</div>
        <div><i class="fa-solid fa-circle-exclamation text-danger"></i></div>
    </div>
    <div class="text-muted small text-truncate fs-9" title="${errorMessage}">${errorMessage}</div>
`;

        errorsContainer.appendChild(item);
    }

    window.updateMainStatus = function (message) {
        const statusText = document.getElementById('download-status-text');
        if (statusText) {
            statusText.textContent = message;
        }
    }

    window.updateTotalProgress = function (downloaded, total, startTime) {
        const progressBar = document.getElementById('download-total-progress');
        const speedElement = document.getElementById('download-speed');
        const etaElement = document.getElementById('download-eta');

        if (!progressBar || !speedElement || !etaElement) return;

        if (total > 0) {
            const percentage = Math.min(Math.round((downloaded / total) * 100), 100);
            progressBar.style.width = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', percentage);
        }

        const elapsedSeconds = (Date.now() - startTime) / 1000;
        if (elapsedSeconds > 0) {
            const bytesPerSecond = downloaded / elapsedSeconds;
            speedElement.textContent = `${formatBytes(bytesPerSecond)}/s`;

            if (total > 0 && bytesPerSecond > 0) {
                const remainingBytes = total - downloaded;
                const etaSeconds = remainingBytes / bytesPerSecond;
                etaElement.textContent = `ETA: ${formatTime(etaSeconds)}`;
            } else {
                etaElement.textContent = 'ETA: calculating...';
            }
        }

        updateMainStatus(`Downloading: ${formatBytes(downloaded)} of ${formatBytes(total)}`);
    }

    window.hideProgressContainer = function () {
        const container = document.getElementById('download-progress-container');
        if (container) {
            container.style.display = 'none';
        }
        // Ensure flag is reset when container is hidden
        window.downloadCancelled = false;
    }
    window.downloadCancelled = false;

    // Function to stop the bulk download process
    window.stopBulkDownload = function () {
        if (window.downloadCompleted) {
            console.log('Download already completed');
            hideProgressContainer();
            return;
        }
        // Set flag to cancel download
        window.downloadCancelled = true;

        console.log('Download cancelled by user');
        updateMainStatus('Download cancelled by user');

        // Hide progress container after a short delay
        setTimeout(function () {
            hideProgressContainer();
            // Reset the flag for future downloads
            window.downloadCancelled = false;
        }, 10000);
    }


    // Main bulk download function
    window.bulkDownload = async function () {

        if (selectedItems.length === 0) {
            console.log('Please select at least one file to download');
            return;
        }
        toggleSpinner();
        window.downloadCancelled = false;
        window.downloadCompleted = false;
        // Reset and show progress UI
        resetProgressUI();

        // Calculate total size from table data directly
        let totalBytes = 0;
        let filesToDownload = [];
        let failedPrepItems = [];

        console.log('Collecting file information from table...');
        updateMainStatus("Collecting file information...");

        try {
            // Get sizes directly from the table data
            const selectedRows = document.querySelectorAll('#tableView tr.table-active');
            selectedRows.forEach(row => {
                const path = row.dataset.path;
                const filename = row.dataset.name;

                // Get the size from the third column (index 2)
                const sizeText = row.cells[2].textContent;
                // Parse the size (this would need to handle 'KB', 'MB', etc. conversions)
                // For simplicity, assuming a function to convert displayed size back to bytes
                const sizeBytes = parseSizeToBytes(sizeText);

                totalBytes += sizeBytes;
                filesToDownload.push({ path, filename, size: sizeBytes });
            });

            // Update UI with total size
            toggleSpinner();
            document.getElementById('download-title').textContent = `Downloading ${filesToDownload.length} files`;
            updateMainStatus(`Starting download: ${formatBytes(totalBytes)}`);

            // Download files in batches
            const zip = new JSZip();
            let processedCount = 0;
            let errorCount = 0;
            let downloadedBytes = 0;
            const startTime = Date.now();

            // Process files in parallel with a limit
            const downloadLimit = 2;
            const downloadChunks = [];

            for (let i = 0; i < filesToDownload.length; i += downloadLimit) {
                downloadChunks.push(filesToDownload.slice(i, i + downloadLimit));
            }

            // Process each chunk
            for (const chunk of downloadChunks) {
                if (window.downloadCancelled) {
                    console.log('Download was cancelled, stopping process');
                    throw new Error('Download cancelled by user');
                }
                const chunkPromises = chunk.map(async (fileInfo) => {
                    try {
                        if (window.downloadCancelled) {
                            throw new Error('Download cancelled by user');
                        }
                        const { path, filename } = fileInfo;

                        // Get pre-signed URL
                        const urlResponse = await fetch(`/get-presigned-url?file_path=${encodeURIComponent(path)}`);
                        if (!urlResponse.ok) {
                            const errorData = await urlResponse.json();
                            throw new Error(errorData.error || 'Failed to get download URL');
                        }

                        const { url } = await urlResponse.json();
                        console.log(`Starting download: ${filename}`);
                        updateMainStatus(`Downloading ${filename}...`);

                        // Download the file
                        const response = await fetch(url);
                        if (!response.ok) {
                            throw new Error(`Failed to download file: ${filename}`);
                        }

                        // Process the stream
                        const reader = response.body.getReader();
                        const chunks = [];
                        let receivedLength = 0;

                        while (true) {
                            if (window.downloadCancelled) {
                                throw new Error('Download cancelled by user');
                            }
                            const { done, value } = await reader.read();

                            if (done) {
                                break;
                            }

                            chunks.push(value);
                            receivedLength += value.length;
                            downloadedBytes += value.length;

                            // Update progress
                            updateTotalProgress(downloadedBytes, totalBytes, startTime);
                        }

                        // Create file from chunks
                        const chunksAll = new Uint8Array(receivedLength);
                        let position = 0;
                        for (const chunk of chunks) {
                            chunksAll.set(chunk, position);
                            position += chunk.length;
                        }

                        // Add to zip
                        zip.file(filename, new Blob([chunksAll]));
                        processedCount++;

                    } catch (fileError) {
                        console.error(`Error downloading ${fileInfo.filename}:`, fileError);
                        const fileId = `file-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
                        addErrorItem(fileId, fileInfo.filename, fileError.message);
                        errorCount++;
                    }
                });

                await Promise.all(chunkPromises);
            }
            if (window.downloadCancelled) {
                throw new Error('Download cancelled by user');
            }
            if (processedCount === 0) {
                throw new Error('No files could be downloaded');
            }

            // Generate and download zip
            console.log('Creating zip file...');
            updateMainStatus('Creating zip file...');

            const content = await zip.generateAsync({
                type: 'blob',
                compression: "DEFLATE",
                compressionOptions: { level: 6 },
                onUpdate: (metadata) => {
                    updateMainStatus(`Creating zip: ${Math.round(metadata.percent)}%`);
                }
            });

            // Trigger download
            console.log('Starting download...');
            updateMainStatus('Starting download...');

            const url = window.URL.createObjectURL(content);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'bulk_download.zip';

            document.body.appendChild(a);
            a.click();

            // Clean up
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            window.downloadCompleted = true;
            const successMessage = `Downloaded ${processedCount} files${errorCount ? ` (${errorCount} failed)` : ''} - ${formatBytes(content.size)}`;
            console.log(successMessage);
            document.getElementById('download-title').textContent = successMessage;
            updateMainStatus('Downloading Completed !!');

            // Auto-hide timer
            setTimeout(hideProgressContainer, 30000);

            // Clear selection
            deselectAllRows();

        } catch (error) {

            if (error.message !== 'Download cancelled by user') {
                // Your existing error handling
                console.error('Download error:', error);
                updateMainStatus(`Error: ${error.message}`);
            }
        }
    };
    window.downloadFolder = async function (folderPath, folderName) {
        window.downloadCancelled = false;
        window.downloadCompleted = false;
        resetProgressUI();
        console.log('Starting folder download:', folderPath);

        try {
            updateMainStatus("Fetching folder contents...");

            // 1. Get all files under the folder (server must return full paths)
            const response = await fetch(`/list_folder_files?folder_path=${encodeURIComponent(folderPath)}`);
            if (!response.ok) {
                throw new Error('Failed to fetch folder contents');
            }

            const files = await response.json(); // [{ path: "...", size: ..., name: "..." }]
            if (files.length === 0) {
                throw new Error('Folder is empty.');
            }

            const zip = new JSZip();
            let totalBytes = 0;
            files.forEach(f => totalBytes += f.size);
            let downloadedBytes = 0;
            let processedCount = 0;
            let errorCount = 0;
            const startTime = Date.now(); // Track start time for speed calculation

            document.getElementById('download-title').textContent = `Downloading folder: ${folderName}`;
            updateMainStatus(`Starting download: ${formatBytes(totalBytes)}`);

            // Process files in parallel with a limit (like in bulkDownload)
            const downloadLimit = 2;
            const downloadChunks = [];

            for (let i = 0; i < files.length; i += downloadLimit) {
                downloadChunks.push(files.slice(i, i + downloadLimit));
            }

            // Process each chunk
            for (const chunk of downloadChunks) {
                if (window.downloadCancelled) {
                    throw new Error('Download cancelled by user');
                }

                const chunkPromises = chunk.map(async (file) => {
                    try {
                        if (window.downloadCancelled) throw new Error('Download cancelled');

                        updateMainStatus(`Downloading ${file.name}...`);

                        const urlResp = await fetch(`/get-presigned-url?file_path=${encodeURIComponent(file.path)}`);
                        if (!urlResp.ok) throw new Error(`URL fetch failed for ${file.path}`);
                        const { url } = await urlResp.json();

                        const fileResp = await fetch(url);
                        if (!fileResp.ok) throw new Error(`Failed to download ${file.name}`);

                        // Process the stream like in bulkDownload to track progress
                        const reader = fileResp.body.getReader();
                        const chunks = [];
                        let receivedLength = 0;

                        while (true) {
                            if (window.downloadCancelled) {
                                throw new Error('Download cancelled by user');
                            }
                            const { done, value } = await reader.read();

                            if (done) {
                                break;
                            }

                            chunks.push(value);
                            receivedLength += value.length;
                            downloadedBytes += value.length;

                            // Update progress with speed and ETA
                            updateTotalProgress(downloadedBytes, totalBytes, startTime);
                        }

                        // Create file from chunks
                        const chunksAll = new Uint8Array(receivedLength);
                        let position = 0;
                        for (const chunk of chunks) {
                            chunksAll.set(chunk, position);
                            position += chunk.length;
                        }

                        // Preserve folder structure by removing base folder from path
                        const relativePath = file.path.replace(folderPath + "/", "");
                        zip.file(relativePath, new Blob([chunksAll]));
                        processedCount++;

                    } catch (fileError) {
                        console.error(`Error downloading ${file.name}:`, fileError);
                        const fileId = `file-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
                        addErrorItem(fileId, file.name, fileError.message);
                        errorCount++;
                    }
                });

                await Promise.all(chunkPromises);
            }

            if (window.downloadCancelled) {
                throw new Error('Download cancelled by user');
            }

            if (processedCount === 0) {
                throw new Error('No files could be downloaded');
            }

            updateMainStatus("Creating zip file...");

            const content = await zip.generateAsync({
                type: 'blob',
                compression: "DEFLATE",
                compressionOptions: { level: 6 },
                onUpdate: meta => updateMainStatus(`Creating zip: ${Math.round(meta.percent)}%`)
            });

            const zipUrl = URL.createObjectURL(content);
            const a = document.createElement('a');
            a.href = zipUrl;
            a.download = `${folderName}.zip`;
            document.body.appendChild(a);
            a.click();
            URL.revokeObjectURL(zipUrl);
            document.body.removeChild(a);

            window.downloadCompleted = true;
            const successMessage = `Downloaded ${processedCount} files${errorCount ? ` (${errorCount} failed)` : ''} - ${formatBytes(content.size)}`;
            document.getElementById('download-title').textContent = successMessage;
            updateMainStatus('Download complete!');

            // Auto-hide timer
            setTimeout(hideProgressContainer, 30000);

        } catch (error) {
            if (error.message !== 'Download cancelled by user') {
                console.error('Download error:', error);
                updateMainStatus(`Error: ${error.message}`);
            }
        } finally {
        }
    }

    window.formatBytes = function (bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];

        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // Bulk delete function (optimized)
    window.bulkDelete = function () {

        if (selectedItems.length === 0) {
            console.log('Please select at least one file to delete');
            return;
        }
        toggleSpinner();
        if (!confirm(`Are you sure you want to delete ${selectedItems.length} file(s)? This cannot be undone.`)) {
            toggleSpinner();
            return;
        }

        console.log(`Deleting ${selectedItems.length} files...`);

        fetch('/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: selectedItems }),
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        toggleSpinner();
                        throw new Error(data.error || 'Failed to delete files');
                    });
                }
                toggleSpinner();
                return response.json();
            })
            .then(data => {
                console.log(data.message);
                toggleSpinner();
                deselectAllRows();
                window.location.href = '/';

            })
            .catch(error => {
                toggleSpinner();
                console.error('Delete error:', error);
            });
    };

    // Initial Fetch
    fetchFileList(rootFolderPath);

    const moveSection = document.getElementById('moveSection');
    const copySection = document.getElementById('copySection');
    const moveFolderList = document.getElementById('moveFolderList');
    const copyFolderList = document.getElementById('copyFolderList');
    
    window.selectedPath = '';
    window.selectedOperation = '';

    window.cancelOperation = function (){
        setTimeout(() => {
            toggleSpinner();
        }, 500);
        window.selectedPath = '';
        window.selectedName = '';
        window.selectedOperation = '';
        withFiles.classList.remove('d-none');
        noFiles.classList.add('d-none');
        noFilesFolder.classList.add('d-none');
        newFolder.classList.add('d-none');
        renameSection.classList.add('d-none');
        copySection.classList.add('d-none');
        moveSection.classList.add('d-none');
        toggleSpinner();
        showToast('Operation cancelled');
    }

    window.moveFolder = function (path, name) {
        window.selectedOperation = 'move';
        window.selectedPath = path;
        withFiles.classList.add('d-none');
        noFiles.classList.add('d-none');
        noFilesFolder.classList.add('d-none');
        newFolder.classList.add('d-none');
        renameSection.classList.add('d-none');
        copySection.classList.add('d-none');
        moveSection.classList.remove('d-none');
        moveFolderList.innerHTML = '';
        loadFolders(currentPath);
    }
    window.copyFolder = function (path, name) {
        window.selectedOperation = 'copy';
        window.selectedPath = path;
        withFiles.classList.add('d-none');
        noFiles.classList.add('d-none');
        noFilesFolder.classList.add('d-none');
        newFolder.classList.add('d-none');
        renameSection.classList.add('d-none');
        copySection.classList.remove('d-none');
        moveSection.classList.add('d-none');
        copyFolderList.innerHTML = '';
        loadFolders(currentPath);
    }

    window.bulkMove = function () {
        window.selectedOperation = 'move';
        window.selectedPath = selectedItems;
        console.log('Copying files:', selectedItems);
        withFiles.classList.add('d-none');
        noFiles.classList.add('d-none');
        noFilesFolder.classList.add('d-none');
        newFolder.classList.add('d-none');
        renameSection.classList.add('d-none');
        copySection.classList.add('d-none');
        moveSection.classList.remove('d-none');
        moveFolderList.innerHTML = '';
        loadFolders(currentPath);
    }

    window.bulkCopy = function () {
        window.selectedOperation = 'copy';
        window.selectedPath = selectedItems;
        console.log('Copying files:', selectedItems);
        withFiles.classList.add('d-none');
        noFiles.classList.add('d-none');
        noFilesFolder.classList.add('d-none');
        newFolder.classList.add('d-none');
        renameSection.classList.add('d-none');
        copySection.classList.remove('d-none');
        moveSection.classList.add('d-none');
        copyFolderList.innerHTML = '';
        loadFolders(currentPath);
    }


    // Load folders for modal
    window.loadFolders = function (path) {
        toggleSpinner();
        console.log('Loading folders for path:', path);
        fetch(`/list_folders/${encodeURIComponent(path)}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 200) {
                    if (selectedOperation === 'copy'){
                        document.getElementById('copyToPath').value = path;
                        document.getElementById('copyFromPath').value = selectedPath;
                    }else{
                        document.getElementById('moveToPath').value = path;
                        document.getElementById('moveFromPath').value = selectedPath;
                    }
                    
                    const folders = data.folders;
                    const folderList = moveSection.classList.contains('d-none') ? copyFolderList : moveFolderList;
                    folderList.innerHTML = '';
                    if (folders.length === 0) {
                        const noFoldersRow = `<tr><td colspan="2" class="text-center">No folders to show</td></tr>`;
                        folderList.innerHTML = noFoldersRow;
                    }else{
                        folders.forEach(folder => {
                            let row = `<tr>
                                <td class='align-middle'><i class="fa-solid fa-folder me-2"></i>${folder.name}</td>
                                <td class="text-end">
                                    <button class="btn btn-sm btn-outline-dark fs-9" data-path="${folder.path}" onclick="loadFolders('${folder.path}')"><i class="fa-solid fa-arrow-right"></i></button>
                                </td>
                            </tr>`;
                            folderList.innerHTML += row;
                        });
                    }
                    
                    updateBreadcrumbOperations(path);
                    toggleSpinner();
                } else {
                    console.error('Error loading folders:', data.error);
                    toggleSpinner();
                }
            })
            .catch(error => {
                console.error('Error fetching folders:', error);
                toggleSpinner();
            });
    }

    function updateBreadcrumbOperations(path) {
        const breadcrumbElements = [
            document.getElementById('breadcrumbCopy'),
            document.getElementById('breadcrumbMove'),
        ];
    
        breadcrumbElements.forEach(breadcrumb => {
            if (!breadcrumb) return;
            breadcrumb.innerHTML = ''; // Clear existing breadcrumbs
            const segments = path.split('/').filter(segment => segment);
    
            let accumulatedPath = '';
            segments.forEach((segment, index) => {
                // Determine the display name
                let displayName;
                if (index === 0) {
                    // For the first segment, remove the leading number and replace underscores with spaces
                    displayName = segment.replace(/^\d+_/, '').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                } else {
                    // For other segments, capitalize the first letter
                    displayName = segment.charAt(0).toUpperCase() + segment.slice(1);
                }
    
                // Update the accumulated path
                accumulatedPath += segment + '/';
    
                // Create the breadcrumb item
                const li = document.createElement('li');
                li.className = 'breadcrumb-item';
    
                if (index === segments.length - 1) {
                    // Last item: render as plain text
                    li.classList.add('active');
                    li.setAttribute('aria-current', 'page');
                    li.textContent = displayName;
                } else {
                    // Other items: render as links
                    const link = `<a href="javascript:void(0)" class="text-decoration-none" 
                    onclick="loadFolders('${accumulatedPath}')" data-path="${accumulatedPath}" title="${displayName}" style="max-width: 200px;">${displayName}</a>`;
                    li.innerHTML=link;
                }
    
                breadcrumb.appendChild(li);
            });
        });
    }
});