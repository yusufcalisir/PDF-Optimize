


# PDF Optimize Aracı 🗜️
https://pdf-optimize-3.onrender.com/
![PDF Optimize Tool](https://i.hizliresim.com/17p4t08.png)

A powerful and modern web application to compress and optimize PDF files. Built with **Flask** for the backend and **HTML, CSS, JS** for the frontend, offering a seamless user experience for file upload, compression, and download.

## ✨ Key Features

### Core Functionality

- 🎯 **Upload PDF Files**: Easily upload PDF files from your local device
- ⚡ **PDF Compression**: Automatically compress your PDF files while maintaining the best possible quality
- 🖱️ **Download PDF**: Download the optimized PDF file after compression

### User Interface

- 🎨 **Modern Design**: Simple, intuitive, and user-friendly layout
- 📶 **Progress Bar**: Real-time progress bar while the file is being processed
- 🔄 **Responsive**: Mobile-friendly and supports all screen sizes

### Output Options

- 📋 **Download Optimized PDF**: Download the compressed version of your PDF after the process is complete

## 🛠️ Technical Stack

### Frontend

- **HTML**: Structuring the webpage
- **CSS**: Styling using modern, responsive design principles
- **JavaScript**: Handling UI events such as file uploads and progress bar updates

### Backend

- **Python**: Using Flask for backend server logic
- **pikepdf**: Python library to work with PDF files and optimize them

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.8 or higher

### Required Python Libraries

To get started with the backend, you will need to install the following libraries:

```bash
pip install flask
pip install pikepdf
pip install werkzeug
````

* **Flask**: Web framework for building the application
* **pikepdf**: PDF manipulation and compression
* **werkzeug**: Utilities for working with file uploads

## 🚀 Installation Guide

### Backend Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yusufcalisir/PDF-Optimize.git
   cd pdf-optimizer
   ```

2. **Install Dependencies**

   Install the required libraries listed above:

   ```bash
   pip install flask
   pip install pikepdf
   pip install werkzeug
   ```

3. **Start the Server**

   ```bash
   python app.py
   ```

   The application will run at `http://127.0.0.1:5000`

### Frontend Setup

No special setup is needed for the frontend since it is integrated with Flask. Simply run the backend server to access the frontend.

## 💡 Usage Guide

1. **Uploading a PDF**

   * Click on the "PDF Seç" button to choose a PDF file from your device.
   * The file will be uploaded and processed.

2. **Progress and Compression**

   * While the PDF is being processed, a progress bar will indicate the status.
   * Once completed, the button will change to "İndir" for you to download the optimized PDF.

3. **Download the Optimized PDF**

   * After compression, you can download the optimized PDF by clicking the "İndir" button.

## 🔧 Configuration

### Environment Variables

There are no special configuration requirements for this application, but you may want to configure the following:

* **UPLOAD\_FOLDER**: The folder where uploaded PDF files will be stored temporarily before processing.
* **SECRET\_KEY**: Set this to a random string for Flask session management (e.g., for flash messages).

## 🐛 Troubleshooting

### Common Issues

1. **File Upload Issues**

   * Ensure you are uploading a valid PDF file.
   * Make sure the file size does not exceed any limit set by the server (adjustable in `app.py`).

2. **PDF Compression Not Working**

   * Ensure you have `pikepdf` installed and properly configured.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

* Flask for web development
* pikepdf for PDF compression
* All contributors and users of this project





